/** Signal only; no identity, token or private content is stored/broadcast. */
export const AUTH_CHANGE = "ni:auth-change";
export const AUTH_CHANGE_STORAGE = "ni:auth-change-at";
export function announceAuthChange() {
  window.dispatchEvent(new Event(AUTH_CHANGE));
  try { localStorage.setItem(AUTH_CHANGE_STORAGE, crypto.randomUUID()); } catch { /* storage unavailable */ }
}
