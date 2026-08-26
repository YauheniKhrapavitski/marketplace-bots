import type { CutterFieldKey, CutterPayload } from "@/lib/fields";

export type FieldOverride = {
  fieldName: CutterFieldKey;
  value: string | number | null;
};

export type MergedPayload = {
  visible: CutterPayload;
  changedFields: CutterFieldKey[];
};

export function mergeSourceWithOverrides(
  sourcePayload: CutterPayload,
  overrides: FieldOverride[]
): MergedPayload {
  const visible = { ...sourcePayload };
  const changedFields: CutterFieldKey[] = [];

  for (const override of overrides) {
    visible[override.fieldName] = override.value;
    changedFields.push(override.fieldName);
  }

  return { visible, changedFields };
}
