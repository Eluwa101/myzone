import { useEffect, useState } from "react";
import { isServerWaking, subscribeServerWaking } from "../api/client";

export function useServerWaking(): boolean {
  const [waking, setWaking] = useState(isServerWaking);

  useEffect(() => subscribeServerWaking(setWaking), []);

  return waking;
}
