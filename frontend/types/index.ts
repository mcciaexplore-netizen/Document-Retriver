export type User = { id: number; name: string; email: string; role: string };
export type Workspace = {
  id: number;
  name: string;
  description?: string;
  file_count?: number;
  record_count?: number;
};
export type FileRecord = {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  source_type: string;
  upload_date: string;
  processing_status: string;
  indexed_records: number;
  error?: string;
};
export type Evidence = {
  result_id: number;
  record_version?: string;
  score: number;
  value: string;
  content: string;
  matched_text: string;
  file: { id: number; name: string; type: string };
  location: Record<string, any>;
  citation: any;
  uploaded_at?: string;
  source_timestamp?: string;
  header?: string;
};
