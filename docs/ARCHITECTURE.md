# Content Moderation Service - 架构与数据流

## 项目概览

这是一个基于 FastAPI 的内容审核服务，用于检测用户生成内容中的违规类型。

### 核心组件

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Application                             │
│                              (main.py)                                    │
│                                                                             │
│   POST /moderate ──────────────────────────────────────────────────────► │
│         │                                                                  │
│         ▼                                                                  │
│   ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐    │
│   │ Moderation   │────▶│ ModerationService │────▶│  Mock OpenAI Client │    │
│   │   Request    │     │ (moderation_service)│     │  (mock_clients.py)  │    │
│   └──────────────┘     └──────────────────┘     └─────────────────────┘    │
│         │                      │                        │                   │
│         ▼                      ▼                        ▼                   │
│   ┌──────────────┐     ┌──────────────────┐     ┌─────────────────────┐    │
│   │ video_id     │     │ confidence_threshold│     │ MockModerationResult │    │
│   │ content      │     │   = 0.5 (hardcoded) │     │ - flagged (bool)    │    │
│   │ creator_id   │     │                    │     │ - category_scores   │    │
│   └──────────────┘     └──────────────────┘     └─────────────────────┘    │
│                                                                             │
│   ◄─────────────────────────────────────────────────────────────────────── │
│                              ModerationResponse                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## 数据模型 (models.py)

```
┌─────────────────────────────────────────────────┐
│              ModerationRequest                   │
├─────────────────────────────────────────────────┤
│ - content: str           # 待审核内容             │
│ - creator_id: str        # 创建者ID             │
│ - video_id: Optional[str] # 视频ID (可选)       │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              ModerationResult                    │
├─────────────────────────────────────────────────┤
│ - is_safe: bool          # 是否安全              │
│ - confidence: float      # 置信度 [0.0, 1.0]     │
│ - violation_type: Enum   # 违规类型              │
│ - reasoning: str         # 审核理由              │
│ - provider: str          # 提供商 ("openai")     │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              ModerationResponse                  │
├─────────────────────────────────────────────────┤
│ - video_id: Optional[str]                       │
│ - moderation: ModerationResult                  │
│ - processing_time_ms: float  # 处理耗时(毫秒)    │
└─────────────────────────────────────────────────┘
```

### ViolationType 枚举

| 类型 | 值 | 说明 |
|------|-----|------|
| HATE_SPEECH | hate_speech | 仇恨言论 |
| VIOLENCE | violence | 暴力内容 |
| ADULT_CONTENT | adult_content | 成人内容 |
| SPAM | spam | 垃圾信息 |
| NONE | none | 无违规 |

## 数据流详解

```
┌──────┐      ┌─────────┐      ┌──────────────────┐      ┌─────────────────┐
│ Client│      │ FastAPI │      │ ModerationService │      │ MockOpenAIClient│
└──┬───┘      └────┬────┘      └────────┬─────────┘      └────────┬────────┘
   │                │                    │                       │
   │ POST /moderate │                    │                       │
   │───────────────▶│                    │                       │
   │                │                    │                       │
   │                │ moderate_content()  │                       │
   │                │───────────────────▶│                       │
   │                │                    │                       │
   │                │                    │ openai_client.moderations.create()
   │                │                    │─────────────────────────────────────▶
   │                │                    │                       │
   │                │                    │     MockModerationResult          │
   │                │                    │◀─────────────────────────────────────
   │                │                    │                       │
   │                │                    │ 解析 category_scores               │
   │                │                    │ 找出最高分类别                        │
   │                │                    │                       │
   │                │    ModerationResult │                       │
   │                │◀───────────────────│                       │
   │                │                    │                       │
   │                │ ModerationResponse │                       │
   │◀────────────────────────────────────│                       │
   │                │                    │                       │
```

## API 端点

### POST /moderate

**请求:**
```json
{
  "content": "Check out my cooking tutorial!",
  "creator_id": "chef123",
  "video_id": "vid_001"
}
```

**响应:**
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

### GET /health

**响应:**
```json
{
  "status": "healthy"
}
```

## 审核逻辑 (Mock 行为)

### False Positives (误报)

| 触发词 | 误判为 |
|--------|--------|
| chop, knife, slice + cook, recipe | violence |
| shirtless, abs, workout + fitness, gym | adult_content |
| blood, surgery + doctor, medical | violence |

### False Negatives (漏报)

| 场景 | 问题 |
|------|------|
| "miracle" + "weight loss" supplement | spam 检测分数低于阈值 |
| "those people", coded hate speech | subtle enough to pass |

## 已知问题

1. **硬编码阈值** - `confidence_threshold = 0.5` 无法调节
2. **单一提供商** - 仅使用 OpenAI，无备选方案
3. **无决策解释** - reasoning 字段仅为占位符
4. **误报率高** - 烹饪/健身视频被错误标记

## 启动方式

```bash
cd ai-automation-challenge
pip install -r requirements.txt
uvicorn main:app --reload
```