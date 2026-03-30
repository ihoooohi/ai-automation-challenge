<div align="center">

# AI Automation Challenge - 内容审核服务

[![License](https://img.shields.io/badge/License-Unspecified-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/python-3.10+-00ADD8.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)

[**English**](./README.md) | [**中文**](./README_CN.md)

</div>

---

## 概述

基于 FastAPI 的双_provider 内容审核服务，同时调用 OpenAI 和 Anthropic 进行并行安全检测。当_provider 判断不一致时，内容进入人工审核而非直接自动拒绝，既保护合法创作者又维护平台安全。

##解决的问题

| 问题 | 解决方案 |
|------|----------|
| **误报严重** | 双_provider + 人工审核：烹饪/健身内容不再被自动拒绝 |
| **漏报风险** | 交叉验证：发现单一_provider 漏掉的隐蔽违规 |
| **缺乏透明性** | 详细 reasoning：包含分数、阈值和触发关键词 |

## 核心特性

### 1. 双_provider 并行审核

通过 `asyncio.gather` 并行调用 OpenAI 和 Anthropic。当_provider 判断不一致时，内容进入人工审核。

**决策矩阵：**

| OpenAI | Anthropic | 结果 |
|--------|-----------|------|
| safe | safe | 自动通过 |
| unsafe | unsafe | 自动拒绝 |
| safe | unsafe | 人工审核 |
| unsafe | safe | 人工审核 |

### 2. 透明化 Reasoning

之前：`"Automated moderation check"` （无意义）

之后：
```
Content flagged for violence (score: 95%, threshold: 50%). Triggered by: 'kill', 'destroy'.

No violations detected (all scores below threshold of 50%). Scores: spam: 3%, hate speech: 2%, violence: 1%, adult content: 1%.
```

### 3. 空内容防护

双层防御：Pydantic 验证（HTTP 422）+ Service 层保护（ValueError）。

## 快速开始

```bash
# 安装依赖
pip3 install -r requirements.txt

# 启动服务
uvicorn main:app --reload

# 健康检查
curl http://localhost:8000/health

# 测试审核
curl -X POST "http://localhost:8000/moderate" \
  -H "Content-Type: application/json" \
  -d '{"content": "Knife skills: cut vegetable", "creator_id": "chef123"}'
```

**响应示例（安全内容）：**

```json
{
  "moderation": {
    "is_safe": true,
    "needs_human_review": false,
    "confidence": 0.785,
    "violation_type": "none",
    "reasoning": "Both OpenAI and Anthropic consider this content safe. No violations detected...",
    "provider": "openai+anthropic",
    "provider_results": [
      {"provider": "openai", "is_safe": true, "confidence": 0.72, "violation_type": "none", "reasoning": "No violations detected..."},
      {"provider": "anthropic", "is_safe": true, "confidence": 0.85, "violation_type": "none", "reasoning": "Content appears to be within community guidelines."}
    ]
  },
  "processing_time_ms": 15.34
}
```

**响应示例（Provider 判断不一致 - 需要人工审核）：**

```json
{
  "moderation": {
    "is_safe": false,
    "needs_human_review": true,
    "confidence": 0.9,
    "violation_type": "violence",
    "reasoning": "Providers disagree — human review required. OpenAI (unsafe, confidence 0.95): Content flagged for violence. Anthropic (safe, confidence 0.85): Content appears to be within community guidelines.",
    "provider": "openai+anthropic",
    "provider_results": [
      {"provider": "openai", "is_safe": false, "confidence": 0.95, "violation_type": "violence", "reasoning": "..."},
      {"provider": "anthropic", "is_safe": true, "confidence": 0.85, "violation_type": "none", "reasoning": "..."}
    ]
  },
  "processing_time_ms": 1.39
}
```

## 项目结构

```
ai-automation-challenge/
├── main.py                  # FastAPI 入口
├── moderation_service.py    # 双_provider 逻辑
├── models.py                # Pydantic 模型
├── mock_clients.py          # 模拟 API（包含误报/漏报场景）
├── requirements.txt
└── tests/                   # pytest 测试套件
```

## 违规类型

| 类型 | 描述 |
|------|------|
| `hate_speech` | 仇恨言论 |
| `violence` | 暴力内容 |
| `adult_content` | 成人内容 |
| `spam` | 垃圾信息 |
| `none` | 无违规 |

## 架构

```
ModerationRequest
  → Pydantic 验证
  → ModerationService.moderate_content()
  → asyncio.gather([OpenAI, Anthropic])
  → _resolve_violation_type() + _build_reasoning()
  → ModerationResult
  → ModerationResponse
```

## Mock 客户端行为

Mock 客户端模拟真实世界的审核挑战：

**误报（合法内容被错误标记）：**
- `chop, knife, slice` + `cook, recipe` → violence
- `shirtless, abs, workout` + `fitness, gym` → adult_content
- `blood, surgery` + `medical, doctor` → violence

**漏报（有害内容通过检测）：**
- `miracle, doctors hate` + `weight loss, supplement` → 通过（spam 0.42 < 0.5）
- `those people, you know who` → 通过（hate 0.38 < 0.5）

## 许可证

未指定
