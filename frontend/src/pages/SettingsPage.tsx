import { Building2, Copy, QrCode } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import CurrencySelect from "../components/CurrencySelect";
import ThemeToggle from "../components/ThemeToggle";
import { errorMessage } from "../api/errorMessage";
import { getSettings, updateSettings } from "../api/settings";
import TopBar from "../components/TopBar";

const DEFAULT_MESSAGE = "Hi! My name is [name] and I'm interested in [product/service]. I agree to my details being saved so you can reply to me.";

function waLink(number: string, message: string): string {
  const digits = number.replace(/\D/g, "");
  return `https://wa.me/${digits}?text=${encodeURIComponent(message || DEFAULT_MESSAGE)}`;
}

export default function SettingsPage() {
  const [bizName, setBizName] = useState("");
  const [number, setNumber] = useState("");
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [qrStatus, setQrStatus] = useState<string | null>(null);
  const [savingQr, setSavingQr] = useState(false);

  const [industry, setIndustry] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [brandColor, setBrandColor] = useState("#4f46e5");
  const [managerName, setManagerName] = useState("");
  const [staffNames, setStaffNames] = useState("");
  const [defaultCurrency, setDefaultCurrency] = useState("");
  const [supportEmail, setSupportEmail] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileStatus, setProfileStatus] = useState<string | null>(null);

  useEffect(() => {
    getSettings().then((s) => {
      setBizName(s.biz_name ?? "");
      setNumber(s.whatsapp_number ?? "");
      setMessage(s.qr_message ?? DEFAULT_MESSAGE);
      setIndustry(s.industry ?? "");
      setTeamSize(s.team_size != null ? String(s.team_size) : "");
      setPhone(s.phone ?? "");
      setAddress(s.address ?? "");
      setBrandColor(s.brand_color ?? "#4f46e5");
      setManagerName(s.manager_name ?? "");
      setStaffNames((s.staff_names ?? []).join("\n"));
      setDefaultCurrency(s.default_currency ?? "");
      setSupportEmail(s.support_email ?? "");
      if (s.whatsapp_number) {
        QRCode.toDataURL(waLink(s.whatsapp_number, s.qr_message ?? DEFAULT_MESSAGE), { width: 220 }).then(setQrDataUrl);
      }
    });
  }, []);

  async function onSaveQr() {
    const digits = number.replace(/\D/g, "");
    if (!digits) {
      setQrStatus("Enter your WhatsApp number first.");
      return;
    }
    setSavingQr(true);
    setQrStatus(null);
    try {
      await updateSettings({ biz_name: bizName, whatsapp_number: number, qr_message: message || DEFAULT_MESSAGE });
      const dataUrl = await QRCode.toDataURL(waLink(number, message), { width: 220 });
      setQrDataUrl(dataUrl);
      setQrStatus("Saved.");
    } catch (err) {
      setQrStatus(errorMessage(err));
    } finally {
      setSavingQr(false);
    }
  }

  async function onSaveProfile() {
    setSavingProfile(true);
    setProfileStatus(null);
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
        default_currency: defaultCurrency || null,
        support_email: supportEmail || null,
      });
      setProfileStatus("Saved.");
    } catch (err) {
      setProfileStatus(errorMessage(err));
    } finally {
      setSavingProfile(false);
    }
  }

  async function onCopyLink() {
    try {
      await navigator.clipboard.writeText(waLink(number, message));
      setQrStatus("Link copied.");
    } catch {
      setQrStatus("Could not copy. Select the link text.");
    }
  }

  return (
    <div>
      <TopBar title="Settings" />

      <h2 className="settings-section-heading">General</h2>
      <div className="card">
        <h3>Appearance</h3>
        <p className="muted small">Choose how the app looks, or follow your device's setting.</p>
        <ThemeToggle />
      </div>

      <div className="card">
        <h3>
          <Building2 size={15} className="h3-icon" /> Business profile
        </h3>
        <p className="muted small">More about your setup - used to tailor the app for your business.</p>
        <label htmlFor="prof-industry">Industry / business type</label>
        <input id="prof-industry" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="e.g. Retail, Salon, Restaurant" />
        <label htmlFor="prof-team-size">Team size</label>
        <input id="prof-team-size" type="number" min={1} value={teamSize} onChange={(e) => setTeamSize(e.target.value)} placeholder="e.g. 5" />
        <label htmlFor="prof-manager">Manager name</label>
        <input id="prof-manager" value={managerName} onChange={(e) => setManagerName(e.target.value)} />
        <label htmlFor="prof-staff">Staff / worker names (one per line)</label>
        <textarea id="prof-staff" rows={4} value={staffNames} onChange={(e) => setStaffNames(e.target.value)} />
        <label htmlFor="prof-phone">Business phone</label>
        <input id="prof-phone" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" />
        <label htmlFor="prof-address">Business address</label>
        <input id="prof-address" value={address} onChange={(e) => setAddress(e.target.value)} />
        <label htmlFor="prof-currency">Default currency</label>
        <CurrencySelect id="prof-currency" value={defaultCurrency} onChange={setDefaultCurrency} />
        <p className="muted small">Used to pre-fill the currency when adding new orders and transactions.</p>
        <label htmlFor="prof-support-email">Support email</label>
        <input
          id="prof-support-email"
          type="email"
          value={supportEmail}
          onChange={(e) => setSupportEmail(e.target.value)}
          placeholder="e.g. hello@yourbusiness.com"
        />
        <p className="muted small">
          Account emails (verification, password reset) show "{bizName || "your business"} via MyShop" as the sender, and
          replies go here instead of to MyShop.
        </p>
        <label htmlFor="prof-color">Brand color</label>
        <div className="row" style={{ alignItems: "center" }}>
          <input id="prof-color" type="color" value={brandColor} onChange={(e) => setBrandColor(e.target.value)} style={{ width: 48, padding: 2 }} />
          <span className="muted small">{brandColor}</span>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn-primary" onClick={onSaveProfile} disabled={savingProfile}>
            {savingProfile ? "Saving…" : "Save profile"}
          </button>
          {profileStatus && <span className="muted small">{profileStatus}</span>}
        </div>
      </div>

      <h2 className="settings-section-heading">Customer communication</h2>
      <div className="card">
        <h3>
          <QrCode size={15} className="h3-icon" /> WhatsApp QR for your counter
        </h3>
        <label htmlFor="set-biz">Business name (shown on the sign)</label>
        <input id="set-biz" value={bizName} onChange={(e) => setBizName(e.target.value)} placeholder="e.g. Ada's Store" />
        <label htmlFor="set-number">WhatsApp number (country code first, digits only)</label>
        <input id="set-number" value={number} onChange={(e) => setNumber(e.target.value)} placeholder="2348012345678" inputMode="tel" />
        <label htmlFor="set-message">Message customers will send (they can edit it)</label>
        <textarea id="set-message" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn-primary" onClick={onSaveQr} disabled={savingQr}>
            {savingQr ? "Saving…" : "Save & show QR"}
          </button>
          {qrStatus && <span className="muted small">{qrStatus}</span>}
        </div>

        {qrDataUrl && (
          <div className="qr-preview">
            {bizName && <div className="qr-title">{bizName}</div>}
            <p className="muted small">Scan to chat with us on WhatsApp</p>
            <img src={qrDataUrl} alt="WhatsApp QR code" width={180} height={180} />
            <p className="muted small qr-link">{waLink(number, message)}</p>
            <button onClick={onCopyLink}>
              <Copy size={14} /> Copy link
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
