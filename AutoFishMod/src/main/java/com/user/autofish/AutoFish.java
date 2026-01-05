package com.user.autofish;

import net.minecraft.client.Minecraft;
import net.minecraft.client.settings.KeyBinding;
import net.minecraft.util.text.TextComponentString;
import net.minecraftforge.client.event.sound.PlaySoundEvent;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.Mod.EventHandler;
import net.minecraftforge.fml.common.event.FMLInitializationEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;

@Mod(modid = AutoFish.MODID, name = AutoFish.NAME, version = AutoFish.VERSION)
public class AutoFish {
    public static final String MODID = "autofish";
    public static final String NAME = "Auto Fish Mod";
    public static final String VERSION = "1.0";

    // 状态变量
    private static int recastDelay = 0;
    private static boolean catchFish = false;

    @EventHandler
    public void init(FMLInitializationEvent event) {
        // 注册事件监听
        MinecraftForge.EVENT_BUS.register(this);
    }

    /**
     * 监听声音事件。
     * 在 Minecraft 中，字幕是由声音触发的。
     * 监听 "entity.bobber.splash" 声音等同于识别 "鱼漂溅起水花" 的字幕。
     */
    @SubscribeEvent
    public void onSound(PlaySoundEvent event) {
        // 1.12.2 中鱼咬钩的声音名称
        if ("entity.bobber.splash".equals(event.getName())) {
            Minecraft mc = Minecraft.getMinecraft();
            // 确保玩家存在且正在钓鱼（有鱼漂实体）
            if (mc.player != null && mc.player.fishEntity != null) {
                // 触发收杆标记
                catchFish = true;
                // 可以在这里添加日志输出方便调试
                // System.out.println("Detected fishing splash sound!");
            }
        }
    }

    /**
     * 客户端每帧更新事件。
     * 用于在主线程安全地执行鼠标点击操作。
     */
    @SubscribeEvent
    public void onClientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) return;
        
        Minecraft mc = Minecraft.getMinecraft();
        if (mc.player == null) return;

        // 执行收杆
        if (catchFish) {
            catchFish = false;
            rightClick(mc);
            // 设置延迟，准备重新抛竿 (例如 20 ticks = 1秒)
            recastDelay = 20;
        }

        // 执行重新抛竿
        if (recastDelay > 0) {
            recastDelay--;
            if (recastDelay == 0) {
                rightClick(mc);
            }
        }
    }

    /**
     * 模拟右键点击
     */
    private void rightClick(Minecraft mc) {
        // 使用 KeyBinding 模拟按下使用物品键（默认右键）
        KeyBinding.onTick(mc.gameSettings.keyBindUseItem.getKeyCode());
    }
}
