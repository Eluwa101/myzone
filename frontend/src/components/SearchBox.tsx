import { Search } from "lucide-react";

/** The search field used on every list page - same markup the Customers page
 * had, so the styling stays in one place. */
export default function SearchBox({
  value,
  onChange,
  label,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder: string;
}) {
  return (
    <div className="search-wrap" style={{ flex: 1, minWidth: 200, maxWidth: 420 }}>
      <Search size={16} className="search-icon" aria-hidden="true" />
      <input
        type="search"
        aria-label={label}
        className="search-input"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
