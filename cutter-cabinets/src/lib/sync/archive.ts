export type ExistingSourceItem = {
  sourceUid: string;
  isArchived: boolean;
};

export function findItemsToArchive(
  existingItems: ExistingSourceItem[],
  incomingSourceUids: Iterable<string>
): string[] {
  const incoming = new Set(incomingSourceUids);
  return existingItems
    .filter((item) => !item.isArchived && !incoming.has(item.sourceUid))
    .map((item) => item.sourceUid);
}
