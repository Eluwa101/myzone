import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/errorMessage";
import { updateSettings } from "../api/settings";
import ErrorText from "../components/ErrorText";
import TopBar from "../components/TopBar";

const DEFAULT_COLOR = "#4f46e5";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [industry, setIndustry] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [brandColor, setBrandColor] = useState(DEFAULT_COLOR);
  const [managerName, setManagerName] = useState("");
  const [staffNames, setStaffNames] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await updateSettings({
        industry: industry || null,
        team_size: teamSize ? Number(teamSize) : null,
        phone: phone || null,
        address: address || null,
        brand_color: brandColor || null,
        manager_name: managerName || null,
        staff_names: staffNames
          .split("\n")
          .map((n) => n.trim())
          .filter(Boolean),
      });
      navigate("/customers");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <TopBar title="Tell us about your business" />

      <div className="card">
        <p className="muted small">
          A bit more about your setup helps us tailor the app for you. This takes a minute, and you can always change it
          later from Settings.
        </p>
        <form onSubmit={onSubmit}>
          <label htmlFor="ob-industry">Industry / business type</label>
          <input id="ob-industry" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="e.g. Retail, Salon, Restaurant" />

          <label htmlFor="ob-team-size">Team size</label>
          <input
            id="ob-team-size"
            type="number"
            min={1}
            value={teamSize}
            onChange={(e) => setTeamSize(e.target.value)}
            placeholder="e.g. 5"
          />

          <label htmlFor="ob-manager">Manager name</label>
          <input id="ob-manager" value={managerName} onChange={(e) => setManagerName(e.target.value)} placeholder="Who runs the day-to-day" />

          <label htmlFor="ob-staff">Staff / worker names (one per line)</label>
          <textarea id="ob-staff" rows={4} value={staffNames} onChange={(e) => setStaffNames(e.target.value)} placeholder={"Jane\nKemi\nTunde"} />

          <label htmlFor="ob-phone">Business phone</label>
          <input id="ob-phone" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" placeholder="Contact number" />

          <label htmlFor="ob-address">Business address</label>
          <input id="ob-address" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Street, city" />

          <label htmlFor="ob-color">Brand color</label>
          <div className="row" style={{ alignItems: "center" }}>
            <input id="ob-color" type="color" value={brandColor} onChange={(e) => setBrandColor(e.target.value)} style={{ width: 48, padding: 2 }} />
            <span className="muted small">{brandColor}</span>
          </div>

          <ErrorText message={error} />

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn-primary" type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save & continue"}
            </button>
            <button className="btn-ghost" type="button" onClick={() => navigate("/customers")} disabled={busy}>
              Skip for now
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
