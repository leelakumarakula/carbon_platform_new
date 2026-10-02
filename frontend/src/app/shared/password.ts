const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';

/** Cryptographically random temporary password that satisfies the policy (letters + digits, 16+ chars). */
export function generateTemporaryPassword(length = 16): string {
  const bytes = new Uint32Array(length);
  for (;;) {
    crypto.getRandomValues(bytes);
    const body = Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length]).join('');
    const pw = `${body.slice(0, 8)}-${body.slice(8)}`;
    if (/[A-Za-z]/.test(pw) && /\d/.test(pw)) return pw;
  }
}
