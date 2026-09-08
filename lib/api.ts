export const backendConfigured =
  process.env.NEXT_PUBLIC_BACKEND_CONFIGURED !== "false";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  if (!backendConfigured) {
    throw new ApiError(
      503,
      "The document service is not connected yet. Sign-in and document features will be available once it is connected.",
    );
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      credentials: "include",
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(
      503,
      "The document service is unavailable. Check that the backend is running.",
    );
  }
  if (!response.ok) {
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      typeof window !== "undefined"
    )
      window.dispatchEvent(new Event("mccia:session-expired"));
    let body;
    try {
      body = await response.json();
    } catch {}
    const detail = body?.detail;
    throw new ApiError(
      response.status,
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join("; ")
          : response.status >= 500
            ? "The document service is unavailable. Check that the backend is running, then retry."
            : response.status === 401
              ? "Please sign in to continue."
              : response.status === 403
                ? "Your role does not permit this action."
                : "The request could not be completed. Please try again.",
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
export const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
export function upload(
  files: File[],
  workspace: number,
  duplicate: string,
  progress: (n: number) => void,
  category = "",
): Promise<any> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/files/upload");
    xhr.withCredentials = true;
    const form = new FormData();
    form.append("workspace_id", String(workspace));
    form.append("duplicate", duplicate);
    form.append("category", category);
    form.append(
      "source_type",
      files.some((f) => f.webkitRelativePath) ? "local_folder" : "upload",
    );
    form.append(
      "last_modified",
      JSON.stringify(files.map((f) => new Date(f.lastModified).toISOString())),
    );
    files.forEach((file) => form.append("files", file));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) progress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () =>
      reject(new Error("Upload connection failed. Please try again."));
    xhr.onload = () => {
      if (xhr.status === 401)
        window.dispatchEvent(new Event("mccia:session-expired"));
      let data;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        return reject(
          new Error("Upload failed. Check the backend connection."),
        );
      }
      if (xhr.status >= 400)
        reject(
          new Error(
            typeof data.detail === "string"
              ? data.detail
              : "The upload could not be completed.",
          ),
        );
      else resolve(data);
    };
    xhr.send(form);
  });
}
export async function waitForFiles(
  ids: number[],
  workspace: number,
): Promise<any[]> {
  for (let attempt = 0; attempt < 180; attempt++) {
    const files = await api<any[]>(`/files?workspace_id=${workspace}`);
    const selected = files.filter((f) => ids.includes(f.id));
    if (
      selected.length === ids.length &&
      selected.every(
        (f) => !["uploaded", "processing"].includes(f.processing_status),
      )
    )
      return selected;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Processing is still running. Follow its status in Files.");
}
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
