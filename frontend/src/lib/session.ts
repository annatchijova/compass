// Per-browser COMPASS session id ("anonymous key"). No login: each browser
// gets its own isolated compass, identified by X-Compass-User on every request.
// The id must satisfy the backend allowlist ^[A-Za-z0-9_-]{1,64}$.

export const USER_STORAGE_KEY = "compass-user";
export const USER_ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

const RANDOM_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

/** Generates a URL-safe random id like "u-a1B2c3D4e5F6". */
export function generateUserId(): string {
  const len = 12;
  let out = "";
  const cryptoObj =
    typeof globalThis !== "undefined" ? globalThis.crypto : undefined;
  if (cryptoObj?.getRandomValues) {
    const bytes = new Uint8Array(len);
    cryptoObj.getRandomValues(bytes);
    for (let i = 0; i < len; i++) {
      out += RANDOM_ALPHABET[bytes[i] % RANDOM_ALPHABET.length];
    }
  } else {
    for (let i = 0; i < len; i++) {
      out += RANDOM_ALPHABET[Math.floor(Math.random() * RANDOM_ALPHABET.length)];
    }
  }
  return `u-${out}`;
}

export function isValidUserId(id: string): boolean {
  return USER_ID_PATTERN.test(id);
}

/**
 * Returns the current session id, generating and persisting one on first use.
 * SSR-safe: returns "" when there is no window/localStorage.
 */
export function getUserId(): string {
  if (typeof window === "undefined" || !window.localStorage) return "";
  let id = window.localStorage.getItem(USER_STORAGE_KEY);
  if (!id || !isValidUserId(id)) {
    id = generateUserId();
    window.localStorage.setItem(USER_STORAGE_KEY, id);
  }
  return id;
}

/** Persists a caller-provided id (must already be validated by the caller). */
export function setUserId(id: string): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(USER_STORAGE_KEY, id);
}

/** Generates a fresh id, persists it, and returns it. */
export function rotateUserId(): string {
  const id = generateUserId();
  setUserId(id);
  return id;
}
