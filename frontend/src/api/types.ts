export type PartType =
  | "tma_mold"
  | "tube_rack"
  | "gel_comb"
  | "multi_well_mold"
  | "microfluidic_channel_mold";

export type ExportFormat = "stl" | "step";
export type ValidationSeverity = "error" | "warning";
export type ExportStatus = "planned" | "generated" | "blocked";

export interface PartRequest {
  part_type: PartType;
  source_prompt?: string | null;
  rows?: number | null;
  cols?: number | null;
  well_count?: number | null;
  diameter_mm?: number | null;
  spacing_mm?: number | null;
  depth_mm?: number | null;
  well_width_mm?: number | null;
  well_height_mm?: number | null;
  tube_volume_ml?: number | null;
  notes: string[];
}

export interface TemplateSpec {
  part_type: PartType;
  name: string;
  description: string;
  required_parameters: string[];
  optional_parameters: string[];
  supported_formats: ExportFormat[];
}

export interface ValidationIssue {
  severity: ValidationSeverity;
  code: string;
  message: string;
  field?: string | null;
}

export interface EstimatedDimensions {
  width_mm: number;
  depth_mm: number;
  height_mm: number;
}

export interface GeneratedFile {
  format: ExportFormat;
  filename: string;
  status: ExportStatus;
  message: string;
}

export interface DesignResponse {
  part_request: PartRequest;
  validation: ValidationIssue[];
  template: TemplateSpec;
  estimated_dimensions?: EstimatedDimensions | null;
  exports: GeneratedFile[];
}
