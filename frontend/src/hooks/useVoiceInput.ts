import { useEffect, useRef, useState } from "react";

/**
 * Browser Speech-to-text via the Web Speech API - free, no backend call,
 * same approach the original prototype used for dictation. Chrome/Edge
 * support it; Firefox/Safari largely don't, so `supported` lets callers
 * hide or disable the mic button gracefully.
 *
 * Chrome ends recognition on its own after a few seconds of silence even
 * with continuous=true - we transparently restart it in that case so
 * recording keeps going until the user explicitly stops it. `onStop` fires
 * once for a real, user-initiated stop (not the silent restarts).
 */
export function useVoiceInput(onResult: (transcript: string) => void, onStop?: () => void) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const stoppingRef = useRef(false);

  const SpeechRecognitionCtor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
  const supported = Boolean(SpeechRecognitionCtor);

  useEffect(() => {
    return () => {
      stoppingRef.current = true;
      recognitionRef.current?.stop();
    };
  }, []);

  function start() {
    if (!SpeechRecognitionCtor) return;

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = navigator.language || "en-US";
    recognition.continuous = true;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript + " ";
      }
      onResult(transcript.trim());
    };
    recognition.onerror = (event) => {
      // "no-speech" (silence) and "aborted" (our own stop()) are expected
      // mid-recording; anything else is a real failure, so don't restart.
      if (event.error !== "no-speech" && event.error !== "aborted") {
        stoppingRef.current = true;
      }
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      if (stoppingRef.current) {
        setListening(false);
        onStop?.();
        return;
      }
      start();
    };

    recognitionRef.current = recognition;
    setListening(true);
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setListening(false);
      onStop?.();
    }
  }

  function toggle() {
    if (!SpeechRecognitionCtor) return;

    if (recognitionRef.current) {
      stoppingRef.current = true;
      recognitionRef.current.stop();
      return;
    }

    stoppingRef.current = false;
    start();
  }

  return { listening, supported, toggle };
}
