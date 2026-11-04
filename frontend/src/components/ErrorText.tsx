export default function ErrorText({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="error-text">{message}</p>;
}
