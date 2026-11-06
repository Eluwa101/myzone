import { CURRENCIES } from "../constants/currencies";

export default function CurrencySelect({
  id,
  value,
  onChange,
  allowBlank = true,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  allowBlank?: boolean;
}) {
  const knownCodes = new Set(CURRENCIES.map((c) => c.code));
  const isUnknown = value && !knownCodes.has(value);

  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
      {allowBlank && <option value="">Select currency</option>}
      {isUnknown && <option value={value}>{value}</option>}
      {CURRENCIES.map((c) => (
        <option key={c.code} value={c.code}>
          {c.code} - {c.name}
        </option>
      ))}
    </select>
  );
}
