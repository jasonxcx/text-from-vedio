# B站视频语音识别与摘要系统改进计划

## TL;DR
> **目标**: 实现三大核心改进：语义化音频分段、批量视频添加、阶段分离的任务并发队列
> 
> **主要交付物**:
> - 移除固定时长分段，利用faster-whisper自然语义分段
> - 支持多URL批量添加（文本框/剪贴板/文件导入）
> - 重构Worker架构：下载可并发、转录单线程、摘要可配置并发
> 
> **预估工作量**: 中等偏上（2-3天开发 + 1天测试）
> **并行执行**: YES - 3大功能可独立开发

---

## Context

### 原始需求
用户提出三个改进点：
1. 音频分段只按时长来分太生硬，可能截断在句子中间
2. 需要支持批量添加视频URL
3. 任务排队并发：转录单线程，摘要可并发N个

### 当前架构分析
- **转录**: `transcriber.py:202-382` 的 `transcribe_long_audio` 使用固定600秒分段
- **UI**: `video_list_tab.py:391-426` 仅支持单个URL添加
- **Worker**: `worker.py:504-596` 简单管理，无阶段分离

---

## Work Objectives

### Core Objective
重构任务处理架构，实现基于语义的音频分段、批量视频添加、阶段分离的并发队列管理

### Concrete Deliverables
- 改进后的 `transcriber.py` - 智能语义分段
- 增强的 `video_list_tab.py` - 批量添加UI
- 重构的 `worker.py` + 新增 `task_queue.py` - 阶段队列管理
- 更新的 `config.py` - 新增并发配置项
- 更新的 `settings_tab.py` - 并发数设置UI

### Definition of Done
- [ ] 转录结果自然按语义分段，无截断感
- [ ] 可一次性添加10+个视频URL
- [ ] 转录任务单线程执行，摘要任务可并发3个
- [ ] 所有功能通过自动化测试

### Must Have
- 语义分段不破坏现有转录精度
- 批量添加支持URL去重和错误提示
- 并发控制不导致资源争抢或死锁

### Must NOT Have (Guardrails)
- 不引入外部消息队列（保持纯Python/Qt）
- 不修改数据库Schema
- 不改变现有UI整体布局

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES - 已有tests目录
- **Automated tests**: YES (Tests after)
- **Framework**: pytest

### QA Policy
每个任务完成后需通过Playwright或Python unittest验证

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (独立开发 - 可同时开始):
├── Task 1: 语义分段优化 [quick]
├── Task 2: 批量添加UI基础 [quick]  
├── Task 3: 并发队列架构设计 [deep]
└── Task 4: 配置系统更新 [quick]

Wave 2 (依赖Wave 1):
├── Task 5: Worker重构集成 [unspecified-high]
├── Task 6: 批量添加逻辑实现 [unspecified-high]
├── Task 7: 设置界面更新 [visual-engineering]
└── Task 8: 状态流转优化 [quick]

Wave 3 (集成测试):
├── Task 9: 端到端测试 [unspecified-high]
├── Task 10: 性能测试 [unspecified-high]
└── Task 11: 边界情况处理 [deep]

Wave FINAL (代码审查):
├── Task F1: 代码质量审查 [unspecified-high]
├── Task F2: 功能验证 [unspecified-high]
└── Task F3: 文档更新 [writing]
```

---

## TODOs

- [x] 1. 语义分段优化 - 移除固定时长分段逻辑 ✅

  **What to do**:
  - 修改 `services/transcriber.py` 的 `transcribe_long_audio` 函数
  - 移除基于 `chunk_duration` 的强制分段逻辑
  - 依赖faster-whisper的VAD和自然分段机制
  - 保留长音频处理能力，但改为智能内存管理

  **Must NOT do**:
  - 不修改 `transcribe_audio` 基础函数
  - 不改变返回的数据结构
  - 不引入新的外部依赖

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - **Reason**: 主要是删除和简化代码，逻辑清晰

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 9 (测试)
  - **Blocked By**: None

  **References**:
  - `services/transcriber.py:202-382` - 当前分段实现
  - faster-whisper文档 - VAD和自然分段机制

  **Acceptance Criteria**:
  - [ ] 转录长音频不再出现10分钟截断
  - [ ] 分段边界在句子停顿处
  - [ ] 内存占用不超标（<4GB for 2小时音频）

  **QA Scenarios**:
  ```
  Scenario: 长音频转录无截断
    Tool: Python unittest
    Preconditions: 准备2小时测试音频
    Steps:
      1. 调用 transcribe_long_audio 处理音频
      2. 检查返回的segments列表
      3. 验证没有恰好600秒的边界
    Expected Result: 所有分段都在自然停顿处
    Evidence: .sisyphus/evidence/task-1-transcript-segments.json
  ```

  **Commit**: YES
  - Message: `refactor(transcriber): remove fixed-duration chunking, use semantic segmentation`
  - Files: `services/transcriber.py`

- [x] 2. 批量添加UI基础 - 创建批量添加对话框 ✅

  **What to do**:
  - 在 `ui/video_list_tab.py` 添加"批量添加"按钮
  - 创建 `BatchAddDialog` 类（新文件或内嵌）
  - 支持多行文本输入粘贴URL
  - 显示解析结果预览（成功/失败）

  **Must NOT do**:
  - 不改变现有单条添加功能
  - 不修改主窗口布局
  - 不引入复杂的状态管理

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: []
  - **Reason**: PySide6 UI开发

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 6 (批量逻辑实现)
  - **Blocked By**: None

  **References**:
  - `ui/video_list_tab.py:34-116` - 控制面板创建
  - `ui/video_list_tab.py:391-426` - 添加视频逻辑
  - PySide6 QDialog文档

  **Acceptance Criteria**:
  - [ ] 界面有"批量添加"按钮
  - [ ] 弹窗支持多行文本输入
  - [ ] 显示URL解析预览
  - [ ] 确认后才批量入库

  **QA Scenarios**:
  ```
  Scenario: 批量添加UI正常显示
    Tool: Playwright + Python
    Preconditions: 应用已启动
    Steps:
      1. 点击"批量添加"按钮
      2. 粘贴10个URL到文本框
      3. 验证预览列表显示10个条目
    Expected Result: UI正常渲染，无错误
    Evidence: .sisyphus/evidence/task-2-batch-dialog.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add batch video add dialog`
  - Files: `ui/video_list_tab.py`, `ui/batch_add_dialog.py`

- [x] 3. 并发队列架构设计 - 设计阶段分离的队列系统 ✅

  **What to do**:
  - 设计新的 `TaskQueue` 类（建议新文件 `app/task_queue.py`）
  - 定义三个独立队列：download_queue, transcribe_queue, summary_queue
  - 设计阶段流转状态机
  - 确定并发控制机制

  **Must NOT do**:
  - 不使用外部消息队列（Redis/RabbitMQ）
  - 不过度设计，保持简单
  - 不修改现有Worker类接口

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - **Reason**: 需要深度架构设计，考虑并发和资源管理

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 5 (Worker重构)
  - **Blocked By**: None

  **References**:
  - `app/worker.py:504-596` - 当前WorkerManager
  - Python asyncio/threading文档
  - PySide6 QThreadPool文档

  **Acceptance Criteria**:
  - [ ] 设计文档包含队列架构图
  - [ ] 明确定义状态流转
  - [ ] 确定并发控制策略

  **QA Scenarios**:
  ```
  Scenario: 架构设计评审通过
    Tool: Code review
    Preconditions: 设计文档完成
    Steps:
      1. 审查架构设计文档
      2. 检查状态流转完整性
      3. 验证无竞态条件
    Expected Result: 设计无重大缺陷
    Evidence: .sisyphus/evidence/task-3-design-doc.md
  ```

  **Commit**: NO (设计阶段不提交代码)

- [x] 4. 配置系统更新 - 添加并发配置项 ✅

  **What to do**:
  - 修改 `config.py` 的 `DEFAULT_CONFIG`
  - 添加 `summary.max_concurrency` 配置项
  - 添加 `download.max_concurrency` 配置项
  - 确保向后兼容

  **Must NOT do**:
  - 不删除现有配置项
  - 不改变配置存储格式
  - 不破坏现有配置读取

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - **Reason**: 简单配置添加

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 5, Task 7
  - **Blocked By**: None

  **References**:
  - `config.py:26-66` - 默认配置
  - `config.py:95-106` - 配置合并逻辑

  **Acceptance Criteria**:
  - [ ] 配置项可正常读取
  - [ ] 旧配置自动升级
  - [ ] 配置验证通过

  **QA Scenarios**:
  ```
  Scenario: 配置读写正常
    Tool: Python unittest
    Preconditions: 配置文件存在
    Steps:
      1. 读取 summary.max_concurrency
      2. 设置为5
      3. 重新读取验证
    Expected Result: 配置持久化成功
    Evidence: .sisyphus/evidence/task-4-config-test.log
  ```

  **Commit**: YES
  - Message: `feat(config): add concurrency configuration options`
  - Files: `config.py`

- [x] 5. Worker重构集成 - 实现阶段队列管理 ✅

  **What to do**:
  - 基于Task 3的设计实现 `app/task_queue.py`
  - 重构 `WorkerManager` 使用新的队列系统
  - 实现阶段流转逻辑
  - 集成并发控制

  **Must NOT do**:
  - 不删除现有Worker类
  - 不改变信号接口
  - 不引入破坏性变更

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: 复杂重构，需要保证稳定性

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Task 3, Task 4

  **References**:
  - `app/worker.py` - 当前实现
  - Task 3的设计文档
  - PySide6信号槽机制

  **Acceptance Criteria**:
  - [ ] 转录单线程执行
  - [ ] 摘要可同时执行N个
  - [ ] 状态正确流转
  - [ ] 资源正确释放

  **QA Scenarios**:
  ```
  Scenario: 并发控制正常工作
    Tool: Python integration test
    Preconditions: 添加5个视频任务
    Steps:
      1. 启动所有任务
      2. 监控转录阶段（应单线程）
      3. 监控摘要阶段（应并发N个）
    Expected Result: 并发控制符合配置
    Evidence: .sisyphus/evidence/task-5-concurrency-test.log
  ```

  **Commit**: YES
  - Message: `refactor(worker): implement stage-based task queue with concurrency control`
  - Files: `app/worker.py`, `app/task_queue.py`

- [x] 6. 批量添加逻辑实现 - 完成批量添加后端 ✅

  **What to do**:
  - 实现批量URL解析函数
  - 支持BV号去重
  - 异步获取视频信息（标题、时长）
  - 批量入库操作

  **Must NOT do**:
  - 不阻塞UI主线程
  - 不重复下载已存在视频
  - 不处理无效URL

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: 需要异步处理和错误处理

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Task 2

  **References**:
  - `ui/video_list_tab.py:391-426` - 当前添加逻辑
  - `services/downloader.py` - 视频信息获取
  - `app/database.py:79-88` - 数据库操作

  **Acceptance Criteria**:
  - [ ] 可批量解析10+个URL
  - [ ] 自动去重
  - [ ] 异步获取视频信息
  - [ ] 错误URL有提示

  **QA Scenarios**:
  ```
  Scenario: 批量添加10个视频
    Tool: Python unittest + Playwright
    Preconditions: 准备10个有效URL
    Steps:
      1. 调用批量添加API
      2. 验证数据库插入10条记录
      3. 验证视频信息已获取
    Expected Result: 全部添加成功
    Evidence: .sisyphus/evidence/task-6-batch-add-test.log
  ```

  **Commit**: YES
  - Message: `feat(services): implement batch video add with deduplication`
  - Files: `services/batch_processor.py`, `ui/video_list_tab.py`

- [x] 7. 设置界面更新 - 添加并发数设置 ✅

  **What to do**:
  - 修改 `ui/settings_tab.py`
  - 添加"任务并发"设置组
  - 添加摘要并发数滑块/输入框
  - 添加下载并发数滑块/输入框
  - 实时保存配置

  **Must NOT do**:
  - 不修改其他设置项
  - 不改变设置界面布局风格
  - 不添加无效验证

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: []
  - **Reason**: UI开发

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Task 4

  **References**:
  - `ui/settings_tab.py` - 当前设置界面
  - `config.py` - 配置项
  - PySide6 QSpinBox文档

  **Acceptance Criteria**:
  - [ ] 界面显示并发设置
  - [ ] 数值可调整
  - [ ] 配置实时保存

  **QA Scenarios**:
  ```
  Scenario: 并发设置界面正常
    Tool: Playwright
    Preconditions: 应用已启动
    Steps:
      1. 打开设置Tab
      2. 找到并发设置组
      3. 修改摘要并发数为5
    Expected Result: 设置保存成功
    Evidence: .sisyphus/evidence/task-7-settings-ui.png
  ```

  **Commit**: YES
  - Message: `feat(ui): add concurrency settings in settings tab`
  - Files: `ui/settings_tab.py`

- [x] 8. 状态流转优化 - 细化任务状态管理 ✅

  **What to do**:
  - 扩展状态枚举（添加queue_downloading, queue_transcribing等）
  - 实现状态自动流转
  - 优化状态显示UI

  **Must NOT do**:
  - 不删除现有状态
  - 不改变状态颜色映射
  - 不破坏状态查询

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - **Reason**: 状态管理和UI小改动

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 9
  - **Blocked By**: Task 5

  **References**:
  - `app/worker.py:69-86` - 当前状态定义
  - `ui/video_list_tab.py:216-235` - 状态显示

  **Acceptance Criteria**:
  - [ ] 新增"排队中"状态
  - [ ] 状态自动流转正确
  - [ ] UI显示更新

  **QA Scenarios**:
  ```
  Scenario: 状态流转正确
    Tool: Python unittest
    Preconditions: 创建测试任务
    Steps:
      1. 提交任务
      2. 验证状态: pending → queue_downloading → downloading → ...
      3. 检查每个状态持续时间
    Expected Result: 状态流转无遗漏
    Evidence: .sisyphus/evidence/task-8-state-flow.log
  ```

  **Commit**: YES
  - Message: `feat(worker): add detailed queue states and auto-transition`
  - Files: `app/worker.py`, `ui/video_list_tab.py`

- [x] 9. 端到端测试 - 完整流程测试 ✅

  **What to do**:
  - 编写端到端测试用例
  - 测试完整流程：批量添加→下载→转录→摘要
  - 验证并发控制
  - 测试边界情况

  **Must NOT do**:
  - 不测试真实视频下载（用mock）
  - 不依赖外部服务
  - 不破坏测试隔离性

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: 复杂集成测试

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task F1
  - **Blocked By**: Task 1, Task 5, Task 6

  **References**:
  - `tests/` - 现有测试
  - `tests/test_integration_flow.py` - 集成测试示例

  **Acceptance Criteria**:
  - [ ] 完整流程测试通过
  - [ ] 并发控制验证通过
  - [ ] 错误处理验证通过

  **QA Scenarios**:
  ```
  Scenario: 完整流程测试
    Tool: pytest
    Preconditions: 环境准备完成
    Steps:
      1. 批量添加3个视频
      2. 验证下载并发
      3. 验证转录单线程
      4. 验证摘要并发
    Expected Result: 全部断言通过
    Evidence: .sisyphus/evidence/task-9-e2e-test-report.html
  ```

  **Commit**: YES
  - Message: `test(e2e): add comprehensive end-to-end tests`
  - Files: `tests/test_e2e_improvements.py`

- [x] 10. 性能测试 - 验证性能指标 ✅

  **What to do**:
  - 测试内存占用
  - 测试并发效率
  - 测试队列吞吐量

  **Must NOT do**:
  - 不测试极端负载
  - 不引入性能测试框架

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - **Reason**: 性能验证

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: Task F1
  - **Blocked By**: Task 9

  **References**:
  - Python memory_profiler
  - pytest-benchmark

  **Acceptance Criteria**:
  - [ ] 内存占用<4GB
  - [ ] 并发效率提升30%+
  - [ ] 无内存泄漏

  **QA Scenarios**:
  ```
  Scenario: 性能指标达标
    Tool: Python benchmark
    Preconditions: 准备测试数据
    Steps:
      1. 运行性能测试
      2. 收集内存和CPU数据
      3. 验证指标达标
    Expected Result: 性能指标符合预期
    Evidence: .sisyphus/evidence/task-10-performance-report.md
  ```

  **Commit**: YES
  - Message: `test(perf): add performance benchmarks`
  - Files: `tests/test_performance.py`

- [x] 11. 边界情况处理 - 异常情况测试 ✅

  **What to do**:
  - 处理网络中断
  - 处理磁盘满
  - 处理并发冲突
  - 处理无效输入

  **Must NOT do**:
  - 不引入复杂重试逻辑
  - 不修改核心业务逻辑

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - **Reason**: 需要深入考虑边界情况

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3
  - **Blocks**: Task F1
  - **Blocked By**: Task 9

  **References**:
  - Python unittest.mock
  - PySide6异常处理

  **Acceptance Criteria**:
  - [ ] 网络中断优雅降级
  - [ ] 无效输入有提示
  - [ ] 并发冲突正确处理

  **QA Scenarios**:
  ```
  Scenario: 网络中断处理
    Tool: Python unittest + mock
    Preconditions: 模拟网络环境
    Steps:
      1. 开始下载任务
      2. 模拟网络中断
      3. 验证重试机制
    Expected Result: 任务失败但不崩溃
    Evidence: .sisyphus/evidence/task-11-edge-case-test.log
  ```

  **Commit**: YES
  - Message: `test(edge): add edge case handling tests`
  - Files: `tests/test_edge_cases.py`

---

## Final Verification Wave

- [x] F1. **代码质量审查** ✅
  - 运行 `ruff check .` 无错误
  - 运行 `mypy` 类型检查通过
  - 代码复杂度检查
  - 输出: 代码质量报告

- [x] F2. **功能验证** ✅
  - 手动测试三大功能
  - 验证UI交互
  - 验证配置持久化
  - 输出: 功能验证清单

- [x] F3. **文档更新** ✅
  - 更新README.md
  - 更新AGENTS.md
  - 添加CHANGELOG
  - 输出: 更新后的文档

---

## Commit Strategy

- **Task 1**: `refactor(transcriber): remove fixed-duration chunking`
- **Task 2**: `feat(ui): add batch video add dialog`
- **Task 4**: `feat(config): add concurrency configuration`
- **Task 5**: `refactor(worker): implement stage-based task queue`
- **Task 6**: `feat(services): implement batch video add`
- **Task 7**: `feat(ui): add concurrency settings`
- **Task 8**: `feat(worker): add detailed queue states`
- **Task 9-11**: `test: add comprehensive tests`
- **F1-F3**: `docs: update documentation`

---

## Success Criteria

### Verification Commands
```bash
# 运行所有测试
python -m pytest tests/ -v

# 代码质量检查
ruff check .
mypy .

# 手动验证
python main.py
# 1. 测试批量添加10个URL
# 2. 验证转录无截断
# 3. 验证并发控制
```

### Final Checklist
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 代码质量检查通过
- [ ] 手动功能验证通过
- [ ] 文档已更新
