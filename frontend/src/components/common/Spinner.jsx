export default function Spinner({ size = "md", label = "Loading...", className = "" }) {
  return (
    <div
      className={`spinner-wrapper ${className}`}
      role="status"
      aria-label={label}
    >
      <div className={`spinner spinner-${size}`} />
      <span className="sr-only">{label}</span>
    </div>
  );
}
