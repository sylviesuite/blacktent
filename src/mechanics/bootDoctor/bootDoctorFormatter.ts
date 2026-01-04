import { BootDoctorScanResult } from "./bootDoctorScan";

export interface BootDoctorMessage {
  status: "ok" | "warning";
  title: string;
  message: string;
  url?: string;
}

export function formatBootDoctorResult(result: BootDoctorScanResult): BootDoctorMessage {
  if (result.running) {
    const url = result.url || `http://localhost:${result.port}/`;
    return {
      status: "ok",
      title: "Dev server detected",
      message: `Boot Doctor found a running dev server at ${url}.`,
      url,
    };
  }

  return {
    status: "warning",
    title: "No dev server detected",
    message: "Ports 5173–5180 were scanned and no HTTP process responded.",
  };
}

