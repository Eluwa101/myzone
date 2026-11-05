import { useEffect, useRef, useState } from "react";

/**
 * Browser Speech-to-text via the Web Speech API - free, no backend call,
 * same approach the original prototype used for dictation. Chrome/Edge
 * support it; Firefox/Safari largely don't, so `supported` lets callers
 * hide or disable the mic button gracefully.
 */
export function useVoiceInput(onResult: (transcript: string) => void) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const SpeechRecognitionCtor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
  const supported = Boolean(SpeechRecognitionCtor);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  function toggle() {
    if (!SpeechRecognitionCtor) return;

    if (recognitionRef.current) {
      recognitionRef.current.stop();
      return;
    }

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
    recognition.onerror = () => {
      recognitionRef.current = null;
      setListening(false);
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setListening(false);
    };

    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  return { listening, supported, toggle };
}
