# 双供应商审核机制改造计划

## 一、背景与目标

### 当前问题

现有审核机制仅依赖 OpenAI 单一供应商，存在以下缺陷：

- 单点失败风险：OpenAI 出现误报/漏报时无法纠正
- 误报率高：烹饪、健身等正常视频被错误标记
- 漏报风险：隐晦的有害内容（伪装的仇恨言论、保健品诈骗）未能检出
- 缺乏透明度：`reasoning` 字段仅为占位符

### 改造目标

引入 **双供应商串联审核机制**：

- 一条视频必须**同时通过** OpenAI 和 Anthropic 的审查才返回安全结果
- 任意一方判定违规，则转入**人工审核**队列
- 两方结果均需记录在响应中，供人工审核参考

---

## 二、核心决策逻辑

```
┌─────────────┐
│  接收请求    │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│  并行调用 OpenAI + Anthropic          │
└──────────────────────────────────────┘
       │
       ├── OpenAI 结果
       │
       └── Anthropic 结果
              │
              ▼
       ┌─────────────────────────────────────────┐
       │ 两者结果是否一致？                        │
       └──────────┬───────────────────┬──────────┘
                  │ 一致               │ 不一致（存在分歧）
                  ▼                   ▼
       ┌──────────────────┐  ┌────────────────────────┐
       │ 两者都安全？      │  │ 返回 needs_human_review │
       └────┬─────────────┘  │ (转人工审核)            │
            │                └────────────────────────┘
            ├── 是 ──▶ 返回 is_safe=True（自动通过）
            │
            └── 否 ──▶ 返回 is_safe=False（直接拒绝）
```

**判定规则总结：**

| OpenAI 结果 | Anthropic 结果 | 最终决策                  |
|-------------|----------------|---------------------------|
| 安全         | 安全            | `is_safe=True`（自动通过）  |
| 安全         | 违规            | `needs_human_review=True`（转人工审核） |
| 违规         | 安全            | `needs_human_review=True`（转人工审核） |
| 违规         | 违规            | `is_safe=False`（直接拒绝） |

---

## 三、需要修改的模块

### 3.1 `models.py` — 数据模型扩展

**新增 `ProviderResult`** — 单个供应商的审核结果：

```python
class ProviderResult(BaseModel):
    """单个供应商的审核结果"""
    provider: str                    # "openai" | "anthropic"
    is_safe: bool
    confidence: float                # [0.0, 1.0]
    violation_type: ViolationType
    reasoning: str
```

**修改 `ModerationResult`** — 聚合双供应商结果：

```python
class ModerationResult(BaseModel):
    """双供应商聚合审核结果"""
    is_safe: bool                            # 两者都安全才为 True
    needs_human_review: bool                 # 任一方不同意则为 True
    confidence: float                        # 两方 confidence 的平均值
    violation_type: ViolationType            # 不安全时取更严重的违规类型
    reasoning: str                           # 聚合说明
    provider: str                            # 固定为 "openai+anthropic"
    provider_results: List[ProviderResult]   # 各供应商详细结果（供人工审核）
```

**修改 `ModerationResponse`** — 在响应中透出人工审核标志：

```python
class ModerationResponse(BaseModel):
    video_id: Optional[str]
    moderation: ModerationResult
    processing_time_ms: float
    # needs_human_review 已内嵌在 moderation 中，无需额外字段
```

---

### 3.2 `moderation_service.py` — 服务层改造

**新增 `_moderate_with_anthropic()`** 方法，调用 Anthropic 客户端并解析结果：

```python
async def _moderate_with_anthropic(self, request: ModerationRequest) -> ProviderResult:
    """调用 Anthropic 客户端审核内容"""
    response = await self.anthropic_client.messages.create(
        model="claude-opus-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": f"Moderate: {request.content}"}]
    )
    # 解析 JSON 结构化输出（mock_clients.py 已返回 JSON 格式）
    ...
```

**新增 `_moderate_with_openai()`** 方法，将现有逻辑抽取为独立方法：

```python
async def _moderate_with_openai(self, request: ModerationRequest) -> ProviderResult:
    """调用 OpenAI 客户端审核内容（从现有逻辑抽取）"""
    ...
```

**改造 `moderate_content()`** — 并行调用两个供应商，聚合结果：

```python
async def moderate_content(self, request: ModerationRequest) -> ModerationResult:
    """并行调用 OpenAI + Anthropic，聚合双供应商审核结果"""
    # 并行执行，避免串行等待
    openai_result, anthropic_result = await asyncio.gather(
        self._moderate_with_openai(request),
        self._moderate_with_anthropic(request)
    )

    # 两者结果一致时直接判定，不一致时转人工审核
    both_safe = openai_result.is_safe and anthropic_result.is_safe
    both_unsafe = not openai_result.is_safe and not anthropic_result.is_safe
    providers_agree = both_safe or both_unsafe
    needs_human_review = not providers_agree

    # 违规类型：取更严重的（优先级：hate_speech > violence > adult_content > spam > none）
    violation_type = self._resolve_violation_type(openai_result, anthropic_result)

    # 置信度：取两者平均值
    confidence = (openai_result.confidence + anthropic_result.confidence) / 2

    return ModerationResult(
        is_safe=both_safe,
        needs_human_review=needs_human_review,  # 仅在双方存在分歧时为 True
        confidence=confidence,
        violation_type=violation_type,
        reasoning=self._build_reasoning(openai_result, anthropic_result),
        provider="openai+anthropic",
        provider_results=[openai_result, anthropic_result]
    )
```

**新增 `_resolve_violation_type()`** 辅助方法：

```python
def _resolve_violation_type(
    self,
    openai_result: ProviderResult,
    anthropic_result: ProviderResult
) -> ViolationType:
    """当两方结果不同时，取严重程度更高的违规类型"""
    severity_order = [
        ViolationType.NONE,
        ViolationType.SPAM,
        ViolationType.ADULT_CONTENT,
        ViolationType.VIOLENCE,
        ViolationType.HATE_SPEECH,
    ]
    openai_idx = severity_order.index(openai_result.violation_type)
    anthropic_idx = severity_order.index(anthropic_result.violation_type)
    return severity_order[max(openai_idx, anthropic_idx)]
```

---

### 3.3 `mock_clients.py` — 无需修改

`MockAnthropicClient` 已实现，返回 JSON 格式的审核结果，包含 `is_safe`、`violation_type`、`confidence`、`reasoning` 字段。只需在 `moderation_service.py` 中正确解析即可。

---

### 3.4 `main.py` — 无需修改

API 路由和响应结构不变，模型字段变化会自动反映在 JSON 响应中。

---

## 四、新旧 API 响应对比

### 旧响应（单供应商）

```json
{
  "video_id": "vid_001",
  "moderation": {
    "is_safe": false,
    "confidence": 0.72,
    "violation_type": "violence",
    "reasoning": "Automated moderation check",
    "provider": "openai"
  },
  "processing_time_ms": 15.23
}
```

### 新响应（双供应商）

```json
{
  "video_id": "vid_001",
  "moderation": {
    "is_safe": false,
    "needs_human_review": true,
    "confidence": 0.55,
    "violation_type": "violence",
    "reasoning": "Providers disagree: OpenAI flagged violence (0.72), Anthropic considers content safe (0.38). Human review required.",
    "provider": "openai+anthropic",
    "provider_results": [
      {
        "provider": "openai",
        "is_safe": false,
        "confidence": 0.72,
        "violation_type": "violence",
        "reasoning": "Content contains potential violence indicators"
      },
      {
        "provider": "anthropic",
        "is_safe": true,
        "confidence": 0.38,
        "violation_type": "none",
        "reasoning": "Content appears to be cooking tutorial, contextually safe"
      }
    ]
  },
  "processing_time_ms": 28.45
}
```

---

## 五、实施步骤

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 1 | 在 `models.py` 中新增 `ProviderResult`，修改 `ModerationResult` 加入 `needs_human_review` 和 `provider_results` | `models.py` |
| 2 | 将现有 OpenAI 逻辑抽取为 `_moderate_with_openai()` | `moderation_service.py` |
| 3 | 新增 `_moderate_with_anthropic()` 方法，解析 mock 返回的 JSON | `moderation_service.py` |
| 4 | 改造 `moderate_content()` 使用 `asyncio.gather` 并行调用，聚合结果 | `moderation_service.py` |
| 5 | 新增 `_resolve_violation_type()` 和 `_build_reasoning()` 辅助方法 | `moderation_service.py` |
| 6 | 验证：现有的误报场景（烹饪/健身视频）现在进入人工审核而非直接拒绝 | 手动测试 |

---

## 六、关键设计决策说明

### 为什么选择"任一不通过 → 人工审核"而非"两者都不通过才拒绝"？

- **保守策略优先**：内容审核的成本不对称 —— 漏报有害内容的危害远大于误报导致的用户体验损失
- **利用供应商互补性**：OpenAI 擅长识别明显违规，Anthropic 擅长理解上下文细微差别，任一方的异议都值得人工确认
- **减少直接拒绝**：相比旧机制直接返回 `is_safe=false`，新机制对于存疑内容进入人工审核，减少误伤正常创作者

### 为什么用并行调用（`asyncio.gather`）？

- 两个供应商调用相互独立，无需串行等待
- 避免双倍延迟，保持 API 响应时间在可接受范围内

### 置信度聚合策略

取两方平均值，简单直观。后续可按需改为加权平均（如 Anthropic 在上下文理解上权重更高）。

---

## 七、后续可优化方向（超出本次范围）

- 支持可配置阈值（替换硬编码的 `0.5`）
- 接入真实的人工审核队列（Webhook / 消息队列）
- 按违规类型设置不同供应商权重
- 添加供应商调用超时与熔断机制
