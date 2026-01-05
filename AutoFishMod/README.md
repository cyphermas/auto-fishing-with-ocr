# AutoFish Mod (1.12.2)

这是一个基于 Forge 1.12.2 的自动钓鱼 Mod。

## 原理
虽然你的需求是“识别字幕”，但在 Minecraft Mod 开发中，字幕（Subtitles）是由**声音事件**触发的。
当鱼咬钩时，游戏会播放 `entity.bobber.splash` 声音，并同时显示 "鱼漂溅起水花" 的字幕。
因此，直接监听这个声音事件比通过图像识别（OCR）屏幕上的字幕要准确、快速且稳定得多。

## 目录结构
- `build.gradle`: Gradle 构建配置文件。
- `src/main/resources/mcmod.info`: Mod 信息文件。
- `src/main/java/com/user/autofish/AutoFish.java`: Mod 源代码。

## 如何构建
1. 确保你安装了 **JDK 8** (Minecraft 1.12.2 需要 Java 8)。
2. 确保你安装了 **Gradle**。
3. 在当前目录打开终端。
4. 运行构建命令：
   ```bash
   gradle build
   ```
5. 构建完成后，在 `build/libs` 目录下找到生成的 `.jar` 文件。
6. 将 `.jar` 文件放入你的 Minecraft `.minecraft/mods` 文件夹中即可。

## 功能
- 自动监听鱼咬钩的声音。
- 听到声音后自动收杆。
- 延迟 1 秒后自动重新抛竿。
