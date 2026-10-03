/** 投稿の本文の最大文字数(前後の空白を除いた長さ) */
export const CONTENT_MAX_LENGTH = 500;

/** 画像の最大サイズ(要件定義書 3.4) */
export const IMAGE_MAX_BYTES = 5 * 1024 * 1024;

/** 投稿できる画像の形式(要件定義書 3.4) */
export const IMAGE_ACCEPT_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];

/** 表示名の最大文字数(4次) */
export const DISPLAY_NAME_MAX_LENGTH = 50;
