export type FieldErrors = Partial<Record<"username" | "password" | "passwordConfirmation", string>>;

const USERNAME_RE = /^[a-z0-9._-]{3,32}$/;

export function validateLogin(username: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!USERNAME_RE.test(username)) {
    errors.username = "Username must be 3-32 chars: lowercase letters, digits, . _ -";
  }
  if (password.length < 10) {
    errors.password = "Password must be at least 10 characters";
  }
  return errors;
}

export function validateRegister(
  username: string,
  password: string,
  passwordConfirmation: string,
): FieldErrors {
  const errors = validateLogin(username, password);
  if (passwordConfirmation.length < 10) {
    errors.passwordConfirmation = "Password confirmation must be at least 10 characters";
  } else if (password !== passwordConfirmation) {
    errors.passwordConfirmation = "Passwords do not match";
  }
  if (username && password.toLowerCase().includes(username.toLowerCase())) {
    errors.password = "Password must not contain the username";
  }
  return errors;
}
