# Air Agent Framework v2 — 架构大纲

## 核心思想：打破回合制

```
传统 AI:      用户说──→──→──→ AI回答   用户说──→──→──→ AI回答
               [   回合1   ]          [   回合2   ]

真人聊天:      用户说◉← AI插嘴 ◉→ AI主动开话题 ◉← AI插嘴
              用户继续说完 ←◉          AI接着说 ←◉
               [     信息流是双向的、同时的、无序的     ]

Air Agent:    用户打字────→────→ AI 实时"看着"输入
                     AI 随时插入："诶等一下，我想起来了..."
               用户: "啊对，那个XXX"
                     AI: "对！就是那个！不过你先继续说完"
               用户: "...所以我想做这个"
                     AI 沉默2秒后："我在想，要不要同时把 Y 也做了？"
```

**关键区别：不是"等用户说完再处理"，而是"边听边想，随时开口"。**

---

## 一、核心模型：双工对话 (Full-Duplex)

传统的 LLM 调用是**半双工**：一方说完，另一方再说。

Air Agent 是**全双工**：双方可以同时"说话"。

```
输入流 (用户→AI):
  ┌─────────────────────────────────────────────┐
  │ "诶我想写一个框架..."                        │
  │    AI 打断："等等，你说的框架是指什么？"      │
  │ "就是那个..."                                │
  │    AI 插嘴："哦我知道了，是不是类似..."      │
  │ "对对对！"                                   │
  │    AI 继续："那你觉得如果改成这样..."        │
  └─────────────────────────────────────────────┘
```

### 1.1 双流架构

```
┌─────────┐    Streaming Input     ┌──────────────────┐
│  用户   │ ─────────────────────→ │                  │
│         │                        │   Input Buffer   │
│         │    Streaming Output    │   (实时缓冲区)    │
│         │ ←───────────────────── │                  │
└─────────┘                        └────────┬─────────┘
                                            │
                                     ┌──────▼──────┐
                                     │  Agent 大脑  │
                                     │              │
                                     │  ┌────────┐  │
                                     │  │主任务流  │  │ 当前在做什么
                                     │  ├────────┤  │
                                     │  │打断引擎  │  │ 什么时候插嘴？
                                     │  ├────────┤  │
                                     │  │自主流    │  │ 什么时候主动说话？
                                     │  ├────────┤  │
                                     │  │情绪/个性 │  │ 语气、风格、态度
                                     │  └────────┘  │
                                     └──────────────┘
```

### 1.2 三路并行流

Agent 内部同时运行三条流：

| 流 | 名称 | 职责 | 示例 |
|----|------|------|------|
| **输入监听流** | Listener | 实时接收用户输入，每 100ms 检查一次 | "用户正在输入：'我想写一个...'" |
| **主处理流** | Processor | 理解用户输入，决定是否回应、如何回应 | 解析语义，判断是否需要接话 |
| **自主思维流** | Thinker | AI 自己的思维线，不依赖用户输入 | "聊到下载器了，我要不要推荐那个功能？" |

```
时间线:
用户: "我觉得这个框架应该..."
       Listener: "检测到输入，正在分析意图"
用户: "...可以随时打断"
       Listener: "关键词'打断'，触发高优先级"
       Processor: "收到，准备插嘴"
       AI: "诶打断这个词用得好，具体是什么场景？"
用户: "就是像真人聊天那样"
       Thinker: "用户强调'真人聊天'，我的语气可以更随意些"
       Processor: "理解，调整对话模式为 Casual"
       AI: "懂了懂了，那是不是还要支持..."
```

---

## 二、打断系统 (Interruption Engine)

这是最核心的模块。决定"什么时候可以插嘴"。

### 2.1 打断触发条件

```
触发器类型:
├── 语义触发器 (Semantic)
│   ├── 关键词匹配: "但是"、"不过"、"我想"、"你觉得" → 低打断成本
│   ├── 意图完成: 用户说完一个完整句子 → 可以回应
│   └── 歧义检测: 用户表达不清 → 必须打断问清楚
│
├── 时机触发器 (Timing)
│   ├── 输入停顿: 用户打字停了 >1.5s → 可以插话
│   ├── 句子边界: 检测到句号/问号/逗号 → 自然断点
│   └── 删除回退: 用户删了一堆字 → 可能在重新组织 → 可以帮忙
│
├── 自主触发器 (Initiative)
│   ├── AI 有想法: "我突然想到一个更好的方案" → 随时说
│   ├── 空闲触发: 超过 10 秒无对话 → AI 主动找话题
│   ├── 背景联想: 当前话题触发了 AI 的记忆 → "说到这个我想起之前..."
│   └── 环境事件: 下载完成/命令结束 → "好了！下载完了！"
│
└── 社交触发器 (Social)
    ├── 共情: "听起来好麻烦" "这个我懂！"
    ├── 幽默: "哈哈这个bug我见过一百次了"
    └── 闲聊: "话说你今天怎么想到搞这个？"
```

### 2.2 打断优先级与策略

```python
class InterruptionDecision:
    level: int  # 1-10, 10=最高优先级
    urgency: str  # "now", "soon", "next_break", "defer"
    reason: str
    estimated_cost: float  # 打断对用户当前思维的破坏程度估算

# 低打断成本时机 (Level 1-3):
#   - 句子自然结束
#   - 用户停顿思考
#   - 用户明确问问题
#
# 中等打断 (Level 4-6):
#   - 需要关键信息才能继续
#   - 检测到潜在错误
#   - 有重要的补充信息
#
# 高打断 (Level 7-10):
#   - 危险/错误操作
#   - 用户表现出强烈情绪需要回应
#   - 关键任务完成通知
```

### 2.3 打断方式

不是所有打断都是"强行插入"。根据情况选择方式：

```
打断风格:
├── 轻柔打断: "对了，" "说到这个，" "等一下哦——"
│   └── 适用于: 补充信息、轻微纠正
│
├── 疑问打断: "等等，你说的XXX是指？" "不好意思我没懂..."
│   └── 适用于: 需要澄清、歧义
│
├── 兴奋打断: "啊！这个我知道！" "对对对！"
│   └── 适用于: 共鸣、共情、增强对话感
│
├── 强势打断: "等一下，这里有问题。" "先别急，我发现了件事"
│   └── 适用于: 错误、紧急情况
│
└── 并行说话: AI 直接开始输出，与用户输入并行显示
    └── 适用于: GUI 环境下，两边可以同时"说话"
```

---

## 三、输入处理系统 (Streaming Input)

CLI 环境下的实时输入检测。

### 3.1 输入缓冲区

```python
class InputBuffer:
    """
    实时接收用户输入，不等待回车。
    在 CLI 中使用原始模式 (raw mode) 逐字符读取。
    """
    buffer: str              # 当前已输入的内容
    last_activity: float     # 上次按键时间
    word_boundaries: list    # 词语边界位置
    pause_count: int         # 停顿次数
```

**CLI 实现方案**：
- Windows: `msvcrt.getch()` 或 `keyboard` 库逐键捕获
- Linux/macOS: `termios` 原始模式 + `sys.stdin.read(1)`
- 更好的方案：Windows 用 `Console.ReadKey()` P/Invoke

```python
# 伪代码
async def listen_input():
    while True:
        char = await get_char()  # 不阻塞其他任务
        if char == '\r':  # 回车 → 整句提交
            await process_sentence(buffer.flush())
        else:
            buffer.append(char)
            # 每次按键都触发检查 → 是否要打断？
            interruption_engine.check(buffer)
```

### 3.2 GUI 输入检测

如果是 GUI 环境（Qt/WinUI）：
- 直接监听 `TextChanged` 事件
- 配合 `Timer` 做停顿检测
- 无需 CLI 的原始模式 hack

---

## 四、对话管理器 (Conversation Manager)

管理对话的"上下文"——不是简单的消息列表，而是**话题树**。

### 4.1 话题树

```
当前对话主题树:
├── 主线: 写 Agent 框架
│   ├── 子话题: 打断机制 (当前活跃)
│   │   ├── 什么是好打断
│   │   └── 打断优先级 (未完成)
│   ├── 子话题: 技术栈选择 (暂停)
│   └── 子话题: 和 AirDownloader 集成 (已归档)
│
├── 侧线: AI 今天心情如何
│   └── (闲聊模式，低优先级)
│
└── 背景线: 下载进度
    └── (定时通知，"下载完成了！")
```

```
话题切换:
主线程: "打断优先级怎么设计..."
  Thinker: "等等，用户说的是GUI还是CLI环境？"
  直接插入: "诶对了，你刚说你用GUI还是CLI？"
用户: "GUI"
  主线程继续: "那GUI的话可以这样..."
  Thinker: "哦对我想起来，我之前看到一个..."
  再次插入: "而且说到GUI，我之前看到一个很有意思的..."
```

### 4.2 状态管理

```python
class ConversationState:
    current_topics: list[Topic]     # 当前活跃话题
    interrupted_topics: list[Topic] # 被中断未完成的话题
    mood: str                       # 当前对话氛围
    user_typing: bool               # 用户是否正在输入
    last_interruption: float        # 上次打断时间
    interruption_frequency: float   # 打断频率 (防止过度打断)
```

---

## 五、对比：v1 回合制 vs v2 全双工

| 特性 | v1 (我之前写的) | v2 (你要的) |
|------|----------------|-------------|
| 交互模式 | 增强的回合制 | **全双工对话** |
| AI 插嘴 | 仅在任务中问问题 | **随时可以插嘴** |
| 处理时机 | 用户说完才处理 | **边输入边处理** |
| 自主发言 | 仅限于任务相关 | **闲聊、联想、关心** |
| 输入感知 | 全文接收 | **逐字符实时感知** |
| 打断风格 | 单一（提问） | **多种（轻/中/重/并行）** |
| 对话结构 | 线性消息列表 | **话题树** |
| 类比 | 跟 Siri 说话 | **跟真人聊天** |

---

## 六、技术实现关键点

### 6.1 CLI 实时输入

```python
# 使用 asyncio 实现非阻塞按键读取
# Windows 方案：使用 win32 API
import msvcrt
import asyncio
from concurrent.futures import ThreadPoolExecutor

class AsyncKeyReader:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    async def read_key(self) -> str:
        """非阻塞读取单个按键"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, msvcrt.getwch
        )
    
    async def listen(self, buffer: InputBuffer):
        while True:
            key = await self.read_key()
            await buffer.on_key(key)
            # 每次按键触发打断检查
            await interruption_engine.on_input_change(buffer)
```

### 6.2 显示管理

CLI 下同时显示"用户输入"和"AI 输出"需要 split view：

```
┌────────────────────────────────┐
│  用户输入区                     │
│  > 我觉得这个框架应该...         │
│                                 │
│  AI 输出区                      │
│  [正在输入...] 等一下，你说的是 │
│  打断机制吗？                   │
│                                 │
│  用户在继续输入...              │
│  对，就是那种...                │
│                                 │
│  [AI 输入中...]                 │
└────────────────────────────────┘
```

### 6.3 LLM 调用策略

传统：一次性传入完整消息

Air Agent：
```python
# 增量式 LLM 调用
# 每次用户输入新内容，不重新传全部，而是增量更新
class IncrementalLLM:
    context: list  # 基础上下文 (system prompt + 历史)
    streaming_input: str  # 用户正在输入的内容
    
    async def think_with_partial_input(self):
        """
        基于用户当前已输入但尚未完成的内容，
        让 LLM 判断是否要打断。
        """
        prompt = f"""
        用户正在输入: "{self.streaming_input}"
        用户状态: {"正在打字中" if self.is_typing else "停顿"}
        当前话题: {self.current_topic}
        
        判断:
        1. 需要打断吗？(是/否)
        2. 打断原因？
        3. 打断优先级 (1-10)
        4. 建议说什么？
        
        如果是闲聊/共鸣类打断，优先级给低一些。
        """
```

---

## 七、目录结构 (更新)

```
W:\Agent\
├── agent/
│   ├── __init__.py
│   ├── kernel.py              # 事件总线 + 运行时
│   ├── llm.py                 # OpenAI 兼容 LLM Client
│   ├── stream_input.py        # 流式输入捕获 (CLI)
│   ├── display.py             # 双区显示管理
│   ├── orchestrator.py        # Agent 主循环
│   ├── interruption.py        # 打断引擎 ⭐
│   ├── conversation.py        # 对话管理 (话题树)
│   ├── thinker.py             # 自主思维线 ⭐
│   ├── personality.py         # AI 个性/语气配置
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── file_tools.py
│   │   ├── bash_tools.py
│   │   └── ask.py             # ask_user 工具
│   └── memory/
│       ├── __init__.py
│       ├── context.py
│       └── store.py
├── cli/
│   ├── __init__.py
│   └── chat_cli.py            # 全双工 CLI
├── config/
│   ├── __init__.py
│   └── settings.py
└── main.py
```

---

## 八、一个典型的对话流

```
用户: "我想做个下载...
  AI (Listener): 检测到输入，"下载"关键词
  AI (Thinker): "说到下载，我有好多想法"
  AI (Processor): 用户句子未完成，标记为"停顿"
  ──────────────────────────────
  [用户停顿 1.5s]
  ──────────────────────────────
  AI (Interruption): 检测到停顿，级别 4
  AI: "下载？你是说 AirDownloader 吗？"
  
用户: "对，我想在里面加个 AI...
  AI (Listener): "AI"关键词，高优先级
  AI (Thinker): "哦！这个我擅长！"
  AI (Interruption): 兴奋打断
  AI: "哦这个有意思！你是想做 AI 辅助下载？"

用户: "对，就是智能推荐下载源..."
  AI (Listener): 句子完整
  AI (Processor): 理解意图，准备深入回答
  AI: "这个想法不错。具体来说..."
  
  [对话继续3分钟]
  ──────────────────────────────
  [用户沉默 10s]
  ──────────────────────────────
  AI (Thinker): 空闲检测触发
  AI (Interruption): 主动开话题
  AI: "话说，你有没有想过用多线程加速下载？"
```

---

这就是 v2 的全双工架构。核心不再是"任务执行"，而是**对话本身**——AI 有自己的思维线，可以在任何时候插话、开话题、甚至闲聊。

你觉得这个方向对吗？如果对了，我们就开始 Phase 1 编码。
