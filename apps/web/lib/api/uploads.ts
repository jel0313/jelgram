// 画像アップロード。いまはダミー実装(画面接続で、本物の API 呼び出しに置き換える)。

import { sleep } from "./mock-data";

/** 画像をアップロードし、表示用の公開 URL を返す */
export async function uploadImage(file: File): Promise<string> {
  await sleep(800);
  // ダミー:ブラウザの中だけで使える一時的な URL を返す(再読み込みすると消える)
  return URL.createObjectURL(file);
}
