# DeepSchedule

课表桌宠：趴在你桌面右下角的鲸鱼娘，点一下看今天的课，双击听她碎碎念，连敲八下她会暴走。

配套一个 **DSH 技能**（`skill/deepschedule`），让 agent 也能回答「今天有什么课」。

## 它长这样

![预览](app/preview.png)

## 快速开始

1. 解压到一个**你有写权限的目录**（路径别太长，中文也行，但别有 `#` `%` 这类字符）。
2. 双击 **`启动DeepSchedule.vbs`**（不弹黑框）。
3. 第一次打开是空课表，右键 → **导入课表…**，用 `app/模版.xlsx` 填好的那份；
   导入后会问你「今天是第几周第几天」，填 `7，2` 这种，她就翻到对应那张表。

> 依赖：Windows + 已安装 **DeepSeek Harness 桌面版**（借用它自带的 Python 运行时，
> 里面有 Pillow / numpy / tkinter）。启动器会自动去找，找不到会提示你。

## 操作

| 操作 | 结果 |
| --- | --- |
| 单击 | 弹出课程表，再点收起 |
| 双击 | 随机一句碎碎念 + **账户余额**（低于 5 元会喊饿） |
| 连敲 8 下 | 暴走：收起所有框、竖向弹跳、循环音效；再敲 8 下恢复 |
| 拖动 | 挪位置，永远被夹在任务栏上方 |
| 右键 | 今日课程 / 换肤 / 导入皮肤… / 导入课表… / 设置周次… / 退出 |

## 课表格式

每个 sheet 一周，第 1 行表头 `节次 | 上课时间 | 星期一 … 星期日`，第 2 行起一节课一行。
细节见 `app/模版.xlsx` 里的「填写说明」，或 `README-课表格式.md`。

也支持：教务系统导出的 `.xls` / `.html`、以及 CSV（`app/课表模板.csv`）。

## 装成 DSH 技能（可选）

把 `skill/deepschedule` 整个文件夹复制到：

- 某个工作区的 `.agents/skills/` 下（只对这个工作区生效），或
- `%USERPROFILE%\.dsh\skills\`（所有工作区生效）

之后对 agent 说「今天有什么课」，它会加载这个技能。

## 开机自启（可选）

把 `启动DeepSchedule.vbs` 的快捷方式丢进 `Win+R` → `shell:startup` 打开的文件夹。

## 换成你自己的立绘 / 音效

- 立绘：右键 → 导入皮肤…，支持 png/jpg/webp；也可以直接替换 `app/whale.png`。
- 音效：把任意 wav 放到 `app/sounds/rage.wav`（单声道 22kHz 最省）。

## 许可

- 代码（`app/*.py`、`skill/*`）：MIT。
- 立绘来自 [dsh-deep-whale](https://github.com/Small-tailqwq/dsh-deep-whale) 的两套皮肤，
  角色原作 **上善**、女仆二次设计 **ZipZipPipe**、皮肤再设计 **Small-tailqwq**，
  美术按 **CC BY-NC-SA 4.0**：**禁止商用**，署名链见 `NOTICE.md`。
- 内置的 `app/sounds/rage.wav` 是本包用程序合成的，不含任何第三方音频。
