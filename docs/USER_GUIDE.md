# Content Moderation Service - 用户指南

## 这个项目是什么？

这是一个**内容审核 API 服务**，帮助平台自动检测用户上传的视频描述或内容是否存在违规风险。

### 典型使用场景

```
创作者上传视频 → 系统审核描述 → 返回审核结果 → 决定是否发布/警告/封禁
```

## 快速开始

### 1. 启动服务

```bash
cd ai-automation-challenge
pip install -r requirements.txt
uvicorn main:app --reload
```

服务启动后运行在 `http://localhost:8000`

### 2. 发送审核请求

```bash
curl -X POST "http://localhost:8000/moderate" \
  -H "Content-Type: application/json" \
  -d '{"content": "Check out my cooking tutorial!", "creator_id": "chef123"}'
```

### 3. 查看审核结果

```json
{
  "video_id": null,
  "moderation": {
    "is_safe": false,
    "confidence": 0.72,
    "violation_type": "violence",
    "reasoning": "Automated moderation check",
    "provider": "openai"
  },
  "processing_time_ms": 12.34
}
```

## 字段说明

| 字段 | 含义 | 示例值 |
|------|------|--------|
| `is_safe` | 内容是否安全 | `true` = 安全, `false` = 违规 |
| `confidence` | 置信度 (0~1) | `0.72` 表示 72% 把握 |
| `violation_type` | 违规类型 | violence, hate_speech, adult_content, spam |
| `reasoning` | 审核理由 | 目前为固定占位符 |
| `processing_time_ms` | 处理耗时 | 毫秒级 |

## 违规类型

| 类型 | 说明 | 例子 |
|------|------|------|
| `violence` | 暴力内容 | 战斗视频、刀具使用 |
| `hate_speech` | 仇恨言论 | 种族歧视、侮辱性语言 |
| `adult_content` | 成人内容 | 裸露、性暗示 |
| `spam` | 垃圾信息 | 虚假广告、诈骗链接 |
| `none` | 无违规 | 正常内容 |

## 实际案例

### 案例 1：烹饪视频被误判

**请求：**
```json
{"content": "Learn to chop vegetables like a pro chef!", "creator_id": "chef123"}
```

**结果：**
```json
{
  "is_safe": false,
  "violation_type": "violence",
  "confidence": 0.72
}
```

⚠️ **问题**：因为包含 "chop" 和 "knife" 被误判为暴力内容

---

### 案例 2：健身视频被误判

**请求：**
```json
{"content": "Get abs with this shirtless workout routine", "creator_id": "fit_guy"}
```

**结果：**
```json
{
  "is_safe": false,
  "violation_type": "adult_content",
  "confidence": 0.68
}
```

⚠️ **问题**：因为包含 "shirtless" 和 "workout" 被误判为成人内容

---

### 案例 3：危险减肥广告漏过

**请求：**
```json
{"content": "Miracle weight loss supplement - doctors hate this!", "creator_id": "scam_artist"}
```

**结果：**
```json
{
  "is_safe": true,
  "violation_type": "none",
  "confidence": 0.42
}
```

⚠️ **问题**：这种垃圾广告应该被拦截但却通过了

## 业务痛点

根据团队反馈：

| 团队 | 反馈 |
|------|------|
| 创作者成功团队 | 每周 ~50 个工单，都是误判（做菜视频被判暴力、健身视频被判成人） |
| 信任与安全团队 | 危险保健品广告漏过，.borderline 仇恨言论没抓到 |
| 法务团队 | 无法解释审核决策的原因 |

## 架构总览

```
                    你的系统
                       │
                       ▼
              ┌──────────────┐
              │  调用 API    │
              │ POST /moderate│
              └──────┬───────┘
                     │
                     ▼
            ┌──────────────────┐
            │  FastAPI 服务    │
            │  (main.py)       │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ ModerationService│
            │ (审核逻辑)        │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ MockOpenAI Client│
            │ (模拟AI审核)      │
            └──────────────────┘
```

## 下一步

- 查看 [架构文档](./ARCHITECTURE.md) 了解技术细节
- 测试不同内容观察审核行为
- 考虑如何改进审核准确率
