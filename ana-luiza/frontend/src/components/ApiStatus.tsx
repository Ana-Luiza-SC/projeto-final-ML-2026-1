import { useEffect, useState } from "react";
import { getHealth } from "../api/client";

type Status = "checking" | "online" | "offline";

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [message, setMessage] = useState("Verificando API...");

  async function checkStatus() {
    setStatus("checking");
    setMessage("Verificando API...");
    try {
      const health = await getHealth();
      setStatus(health.status === "ok" ? "online" : "offline");
      setMessage(health.status === "ok" ? "API online" : "API respondeu com status inesperado.");
    } catch (error) {
      setStatus("offline");
      setMessage(error instanceof Error ? error.message : "Não foi possível conectar à API.");
    }
  }

  useEffect(() => {
    void checkStatus();
  }, []);

  return (
    <div className={`api-status ${status}`}>
      <span className="status-dot" aria-hidden="true" />
      <span>{message}</span>
      <button type="button" onClick={checkStatus}>Reverificar</button>
    </div>
  );
}
