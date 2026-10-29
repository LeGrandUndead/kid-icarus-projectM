//! Isolated experiment: change the verified USA display scheduler interval.
//! No clock/SVC return-value changes. Disabled unless explicitly requested.
use std::sync::OnceLock;
use zakuro_cpu::Bus;
use crate::System;

fn read64(system: &mut System, address: u32) -> u64 {
    let lo = system.memory.read32(address) as u64;
    let hi = system.memory.read32(address + 4) as u64;
    lo | (hi << 32)
}

pub fn observe(system: &mut System, number: u32) {
    if number != 0x28 {
        return;
    }

    // svcGetSystemTick immediately before and immediately after the
    // scheduler object's callback.
    let pc = system.cpu.current_pc();
    let pre_callback = pc == 0x00991160;
    let post_callback = pc == 0x009911C8;

    // Internal GetSystemTick sites inside the callback at 0x00102EE4.
    // current_pc() is one ARM instruction behind the SVC itself.
    let callback_tick_a = pc == 0x0010329C; // SVC at 0x001032A0
    let callback_tick_b = pc == 0x001034A8; // SVC at 0x001034AC

    if !pre_callback && !post_callback && !callback_tick_a && !callback_tick_b {
        return;
    }

    // the playable 60 fps mode (kiu_frame_rate), unless a research run
    // asked for its own interval
    if std::env::var_os("KIU_TEST_FRAME_INTERVAL").is_none() {
        if pre_callback || post_callback {
            crate::kiu_frame_rate::at_scheduler(system, pre_callback);
        }
        return;
    }

    static OPTIONS: OnceLock<Option<(u32, u64)>> = OnceLock::new();
    let Some(&(interval, from)) = OPTIONS.get_or_init(|| {
        let n = std::env::var("KIU_TEST_FRAME_INTERVAL")
            .ok()?
            .parse::<u32>()
            .ok()?;
        if !(1..=2).contains(&n) {
            return None;
        }
        let from = std::env::var("KIU_TEST_FRAME_INTERVAL_FROM")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(6000);
        Some((n, from))
    }).as_ref() else {
        return;
    };

    if system.kernel.program_id != 0x0004000000030100 {
        return;
    }

    // USA executable / site signatures.
    if system.memory.read32(0x00991164) != 0xEF000028
        || system.memory.read32(0x009911CC) != 0xEF000028
        || system.memory.read32(0x009103BC) != 0xE5952054
        || system.memory.read32(0x009911DC) != 0x00D63824
    {
        return;
    }

    let manager = system.memory.read32(0x00D63824);

    if manager & 3 != 0
        || !(0x00100000..0x20000000).contains(&manager)
    {
        return;
    }

    // At the first SVC r5 is the verified global manager.
    if pre_callback && system.cpu.regs[5] != manager {
        return;
    }

    let frame = system.usage.as_ref().map_or(0, |u| u.frames);

    // Observer-only trace of the two SystemTick paths inside the main
    // callback. Do not alter registers, memory, clocks, or return values.
    if callback_tick_a || callback_tick_b {
        if std::env::var("KIU_TRACE_SCHEDULER").as_deref() == Ok("1") {
            let trace_from = std::env::var("KIU_TRACE_SCHEDULER_FROM")
                .ok()
                .and_then(|s| s.parse::<u64>().ok())
                .unwrap_or(5996);

            let trace_to = std::env::var("KIU_TRACE_SCHEDULER_TO")
                .ok()
                .and_then(|s| s.parse::<u64>().ok())
                .unwrap_or(6008);

            if frame >= trace_from && frame <= trace_to {
                if callback_tick_a
                    && system.memory.read32(0x001032A0) != 0xEF000028
                {
                    return;
                }

                if callback_tick_b
                    && system.memory.read32(0x001034AC) != 0xEF000028
                {
                    return;
                }

                let timer0  = read64(system, 0x00D48358);
                let timer8  = read64(system, 0x00D48360);
                let timer10 = read64(system, 0x00D48368);

                log::warn!(
                    "KIU callback ticksite site={} frame={} cycles={} field50={} interval={} elapsed={} carry={}                      r0={:08X} r1={:08X} r2={:08X} r3={:08X} r4={:08X} r5={:08X}                      r6={:08X} r7={:08X} r8={:08X} r9={:08X} r10={:08X} r11={:08X}                      timer0={} timer8={} timer10={}",
                    if callback_tick_a { "A" } else { "B" },
                    frame,
                    system.cpu.cycles,
                    system.memory.read32(manager + 0x50),
                    system.memory.read32(manager + 0x54),
                    system.memory.read32(manager + 0xB0),
                    system.memory.read32(manager + 0xA8),
                    system.cpu.regs[0],
                    system.cpu.regs[1],
                    system.cpu.regs[2],
                    system.cpu.regs[3],
                    system.cpu.regs[4],
                    system.cpu.regs[5],
                    system.cpu.regs[6],
                    system.cpu.regs[7],
                    system.cpu.regs[8],
                    system.cpu.regs[9],
                    system.cpu.regs[10],
                    system.cpu.regs[11],
                    timer0,
                    timer8,
                    timer10,
                );
            }
        }

        return;
    }

    let object = system.cpu.regs[4];

    // Observer only. Keep it tightly bounded so the normal runtime log stays
    // useful. Nothing in this block writes guest state.
    static TRACE: OnceLock<Option<(u64, u64)>> = OnceLock::new();

    if let Some(&(trace_from, trace_to)) = TRACE.get_or_init(|| {
        if std::env::var("KIU_TRACE_SCHEDULER").as_deref() != Ok("1") {
            return None;
        }

        let from = std::env::var("KIU_TRACE_SCHEDULER_FROM")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(5996);

        let to = std::env::var("KIU_TRACE_SCHEDULER_TO")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(6008);

        Some((from, to))
    }).as_ref() {
        let object_valid =
            object & 3 == 0
            && (0x00100000..=0x1FFFFE00).contains(&object);

        if frame >= trace_from && frame <= trace_to && object_valid {
            let thread = system.kernel.current()
                .map(|t| t.name.clone())
                .unwrap_or_else(|| "?".to_owned());

            let callback = system.memory.read32(object + 0x130);
            let flag = system.memory.read8(object + 0x134);

            let t110 = read64(system, object + 0x110);
            let t118 = read64(system, object + 0x118);
            let t120 = read64(system, object + 0x120);
            let t128 = read64(system, object + 0x128);

            let field50 = system.memory.read32(manager + 0x50);
            let field54 = system.memory.read32(manager + 0x54);
            let counter = system.memory.read32(manager + 0x98);
            let last = system.memory.read32(manager + 0xA0);
            let carry = system.memory.read32(manager + 0xA8);
            let carry2 = system.memory.read32(manager + 0xAC);
            let elapsed = system.memory.read32(manager + 0xB0);

            log::warn!(
                "KIU sched trace phase={} frame={} cycles={} thread={} object={:08X} callback={:08X} flag={} field50={} interval={} counter={} last={} carry={} carry2={} elapsed={} t110={} t118={} t120={} t128={}",
                if pre_callback { "pre" } else { "post" },
                frame,
                system.cpu.cycles,
                thread,
                object,
                callback,
                flag,
                field50,
                field54,
                counter,
                last,
                carry,
                carry2,
                elapsed,
                t110,
                t118,
                t120,
                t128,
            );
        }
    }

    // The display wait overwrites elapsed ticks with its original even-tick
    // rounding. Keep the half-step value visible to consumers between callbacks
    // as well. Do not change timestamp return values or the emulated clock.
    if post_callback && frame >= from && interval == 1 {
        static HALF_STEP_POST: OnceLock<bool> = OnceLock::new();
        if *HALF_STEP_POST.get_or_init(|| {
            std::env::var("KIU_TEST_RESET_CARRY").as_deref() == Ok("1")
                && std::env::var("KIU_TEST_HALF_STEP").as_deref() == Ok("1")
        }) && system.memory.read32(0x00828E30) == 0x3F800000 {
            system.memory.write32(manager + 0xB0, 1);
        }
    }

    // Only the first SVC is the original experimental mutation point.
    if !pre_callback {
        return;
    }

    let previous = system.memory.read32(manager + 0x54);

    if frame >= from
        && (previous == 1 || previous == 2)
        && previous != interval
    {
        log::warn!(
            "KIU interval experiment frame={frame} manager={manager:08X} interval {previous}->{interval}"
        );
        system.memory.write32(manager + 0x54, interval);
    }

    // Research only: test removal of carried scheduler state separately.
    static RESET_CARRY: OnceLock<bool> = OnceLock::new();

    if frame >= from
        && interval == 1
        && *RESET_CARRY.get_or_init(|| {
            std::env::var("KIU_TEST_RESET_CARRY").as_deref() == Ok("1")
        })
        && system.memory.read32(manager + 0x54) == 1
    {
        system.memory.write32(manager + 0xA8, 0);
        system.memory.write32(manager + 0xAC, 0);
        static HALF_STEP: OnceLock<bool> = OnceLock::new();
        if *HALF_STEP.get_or_init(|| std::env::var("KIU_TEST_HALF_STEP").as_deref() == Ok("1"))
            && system.memory.read32(0x00828E10) == 0xED9F0A06
            && matches!(system.memory.read32(0x00828E30), 0x40000000 | 0x3F800000) {
            // This data literal is read by translated update code. It is not
            // an ARM instruction patch or a change to the runtime clock.
            if system.memory.read32(0x00828E30) == 0x40000000 {
                if !system.memory.write32_privileged(0x00828E30, 0x3F800000) {
                    return;
                }
                log::warn!("KIU half-step experiment enabled at frame={frame}");
            }
            system.memory.write32(manager + 0xB0, 1);
        }
    }

    if frame % 600 < 2 {
        log::warn!(
            "KIU scheduler frame={frame} manager={manager:08X} interval={} elapsed={} carry={} counter={} last={}",
            system.memory.read32(manager + 0x54),
            system.memory.read32(manager + 0xB0),
            system.memory.read32(manager + 0xA8),
            system.memory.read32(manager + 0x98),
            system.memory.read32(manager + 0xA0)
        );
    }
}
