import { useState } from "react";
import { useComposer, type Recipient } from "../hooks/useComposer";
import EmailPane from "./EmailPane";
import Tabs from "./Tabs";
import WhatsappPane from "./WhatsappPane";

export type { Recipient };

/** Write once, send either way. One draft, with the same Email | WhatsApp outline
 * wherever messages are written: the compose page, a customer's slide-over, and (as
 * its own tabs) the segment page. This wrapper is for the places that want both
 * channels in one box; the segment page shares the same draft hook and panes. */
export default function Composer({
  recipients,
  segmentId,
  initialTemplateId,
  embedded = false,
}: {
  recipients: Recipient[] | null;
  segmentId?: string | null;
  initialTemplateId?: string | null;
  embedded?: boolean;
}) {
  const composer = useComposer({ recipients, segmentId, initialTemplateId });
  const [tab, setTab] = useState<"email" | "whatsapp">("email");
  const whatsappCount = composer.whatsappRecipients.length;

  return (
    <div className="composer">
      <Tabs
        tabs={[
          { key: "email", label: "Email" },
          { key: "whatsapp", label: whatsappCount > 0 ? `WhatsApp (${whatsappCount})` : "WhatsApp" },
        ]}
        active={tab}
        onChange={(k) => setTab(k as "email" | "whatsapp")}
      />
      {tab === "email" ? <EmailPane composer={composer} embedded={embedded} /> : <WhatsappPane composer={composer} />}
    </div>
  );
}
