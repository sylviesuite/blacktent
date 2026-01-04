import http from "http";

export interface BootDoctorScanResult {
  running: boolean;
  port?: number;
  url?: string;
}

const PORT_RANGE = { start: 5173, end: 5180 };
const REQUEST_TIMEOUT_MS = 1_500;

function probePort(port: number): Promise<boolean> {
  const url = `http://localhost:${port}/`;
  return new Promise((resolve) => {
    const req = http.request(url, { method: "GET" }, (res) => {
      res.destroy();
      resolve(true);
    });

    req.once("error", () => {
      resolve(false);
    });
    req.setTimeout(REQUEST_TIMEOUT_MS, () => {
      req.destroy();
      resolve(false);
    });

    req.end();
  });
}

export async function bootDoctorScan(): Promise<BootDoctorScanResult> {
  for (let port = PORT_RANGE.start; port <= PORT_RANGE.end; port += 1) {
    const ok = await probePort(port);
    if (ok) {
      return {
        running: true,
        port,
        url: `http://localhost:${port}/`,
      };
    }
  }

  return { running: false };
}

