// Remembers that this browser has signed in before, so a visitor without a session
// is sent to sign-up the first time and to sign-in once they have an account.
// Holds no identity, just a flag. localStorage can throw (private mode, blocked
// storage); the visitor then just lands on sign-up, which links to sign-in.

const KNOWN_ACCOUNT_KEY = 'medvault.hasSignedIn';

export function hasKnownAccount(): boolean {
  try {
    return localStorage.getItem(KNOWN_ACCOUNT_KEY) === '1';
  } catch {
    return false;
  }
}

export function rememberKnownAccount() {
  try {
    localStorage.setItem(KNOWN_ACCOUNT_KEY, '1');
  } catch {
    // ignore
  }
}
