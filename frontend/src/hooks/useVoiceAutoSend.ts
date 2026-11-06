import { useEffect, useRef, useState } from "react";
import { useVoiceInput } from "./useVoiceInput";

const AUTO_SEND_SECONDS = 3;

/**
 * Wires dictation (useVoiceInput) to a "Sending in Ns..." auto-send
 * countdown: stopping the mic with text in the box schedules onAutoSend,
 * cancellable by editing the input, clicking the mic again, or sending
 * manually. Shared by every chat-style input (Assistant, Ask your data,
 * the per-customer Assistant tab).
 */
export function useVoiceAutoSend(input: string, setInput: (value: string) => void, onAutoSend: () => void) {
  const [autoSendCountdown, setAutoSendCountdown] = useState<number | null>(null);
  const inputRef = useRef(input);
  const baseTextRef = useRef("");
  const autoSendIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onAutoSendRef = useRef(onAutoSend);

  useEffect(() => {
    inputRef.current = input;
  }, [input]);

  useEffect(() => {
    onAutoSendRef.current = onAutoSend;
  });

  useEffect(() => {
    return () => {
      if (autoSendIntervalRef.current) clearInterval(autoSendIntervalRef.current);
    };
  }, []);

  function cancelAutoSend() {
    if (autoSendIntervalRef.current) {
      clearInterval(autoSendIntervalRef.current);
      autoSendIntervalRef.current = null;
    }
    setAutoSendCountdown(null);
  }

  function scheduleAutoSend() {
    setAutoSendCountdown(AUTO_SEND_SECONDS);
    autoSendIntervalRef.current = setInterval(() => {
      setAutoSendCountdown((n) => {
        if (n === null || n <= 1) {
          if (autoSendIntervalRef.current) clearInterval(autoSendIntervalRef.current);
          autoSendIntervalRef.current = null;
          onAutoSendRef.current();
          return null;
        }
        return n - 1;
      });
    }, 1000);
  }

  const voice = useVoiceInput(
    (transcript) => setInput((baseTextRef.current ? baseTextRef.current + " " : "") + transcript),
    () => {
      if (inputRef.current.trim()) scheduleAutoSend();
    }
  );

  function onMicClick() {
    cancelAutoSend();
    baseTextRef.current = inputRef.current;
    voice.toggle();
  }

  return { voice, autoSendCountdown, cancelAutoSend, onMicClick };
}
