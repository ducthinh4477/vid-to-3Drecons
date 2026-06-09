import type { PlyInfo } from '../api';
import { getPlyInfo } from '../api';

export async function inspectPlyAsset(pathOrUrl: string, known?: PlyInfo): Promise<PlyInfo | null> {
  if (known) return known;
  const url = new URL(pathOrUrl, window.location.href);
  const path = url.searchParams.get('path');
  if (path) return getPlyInfo(path);
  return null;
}
