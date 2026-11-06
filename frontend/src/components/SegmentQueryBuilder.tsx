import { Plus, Trash2 } from "lucide-react";
import type { SegmentCondition, SegmentFieldDef, SegmentFieldsCatalog, SegmentGroup, SegmentNode, SegmentOperator } from "../api/types";

const PURCHASE_ACTIVITY_KEYS = new Set([
  "transaction_count",
  "total_spent",
  "last_purchase_date",
  "first_purchase_date",
  "order_count",
  "has_unpaid_order",
  "has_undelivered_order",
  "last_order_date",
]);

export const OPERATOR_LABELS: Record<SegmentOperator, string> = {
  equals: "is",
  not_equals: "is not",
  contains: "contains",
  not_contains: "doesn't contain",
  in_list: "is one of",
  not_in_list: "is none of",
  is_set: "is set",
  is_not_set: "is not set",
  greater_than: "is greater than",
  less_than: "is less than",
  between: "is between",
  within_last_days: "is within the last (days)",
  over_days_ago: "was more than (days) ago",
};

export const COMBINATOR_LABELS: Record<SegmentGroup["combinator"], string> = {
  and: "ALL (AND)",
  or: "ANY (OR)",
  nor: "NONE (NOR)",
};

export function emptyGroup(): SegmentGroup {
  return { type: "group", combinator: "and", conditions: [] };
}

function fieldDef(fields: SegmentFieldDef[], key: string): SegmentFieldDef {
  if (key.startsWith("extra.")) return { key, label: key.slice(6), type: "text" };
  return fields.find((f) => f.key === key) ?? fields[0];
}

function defaultConditionFor(field: SegmentFieldDef, operator: SegmentOperator): SegmentCondition {
  return { type: "condition", field: field.key, operator, value: field.type === "boolean" ? true : "" };
}

export default function SegmentQueryBuilder({
  group,
  catalog,
  onChange,
}: {
  group: SegmentGroup;
  catalog: SegmentFieldsCatalog;
  onChange: (g: SegmentGroup) => void;
}) {
  return <GroupEditor group={group} catalog={catalog} onChange={onChange} depth={0} />;
}

function GroupEditor({
  group,
  catalog,
  onChange,
  onRemove,
  depth,
}: {
  group: SegmentGroup;
  catalog: SegmentFieldsCatalog;
  onChange: (g: SegmentGroup) => void;
  onRemove?: () => void;
  depth: number;
}) {
  function updateChild(i: number, next: SegmentNode) {
    onChange({ ...group, conditions: group.conditions.map((c, idx) => (idx === i ? next : c)) });
  }
  function removeChild(i: number) {
    onChange({ ...group, conditions: group.conditions.filter((_, idx) => idx !== i) });
  }
  function addCondition() {
    const first = catalog.fields[0];
    const ops = catalog.operators_by_type[first.type] ?? [];
    onChange({ ...group, conditions: [...group.conditions, defaultConditionFor(first, ops[0])] });
  }
  function addGroup() {
    onChange({ ...group, conditions: [...group.conditions, emptyGroup()] });
  }

  return (
    <div className={`segment-group${depth > 0 ? " segment-group-nested" : ""}`}>
      <div className="row-between segment-group-header">
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          <span className="muted small">Match</span>
          <select aria-label="Combinator" value={group.combinator} onChange={(e) => onChange({ ...group, combinator: e.target.value as SegmentGroup["combinator"] })}>
            <option value="and">{COMBINATOR_LABELS.and}</option>
            <option value="or">{COMBINATOR_LABELS.or}</option>
            <option value="nor">{COMBINATOR_LABELS.nor}</option>
          </select>
          <span className="muted small">of:</span>
        </div>
        {onRemove && (
          <button type="button" className="icon-btn btn-ghost" onClick={onRemove} aria-label="Remove group">
            <Trash2 size={14} />
          </button>
        )}
      </div>

      {group.conditions.length === 0 && <p className="muted small">No conditions yet - matches everyone.</p>}

      {group.conditions.map((node, i) =>
        node.type === "group" ? (
          <GroupEditor key={i} group={node} catalog={catalog} onChange={(g) => updateChild(i, g)} onRemove={() => removeChild(i)} depth={depth + 1} />
        ) : (
          <ConditionRow key={i} condition={node} catalog={catalog} onChange={(c) => updateChild(i, c)} onRemove={() => removeChild(i)} />
        )
      )}

      <div className="row" style={{ marginTop: 6, gap: 8 }}>
        <button type="button" className="btn-ghost small" onClick={addCondition}>
          <Plus size={13} /> Condition
        </button>
        <button type="button" className="btn-ghost small" onClick={addGroup}>
          <Plus size={13} /> Group
        </button>
      </div>
    </div>
  );
}

function ConditionRow({
  condition,
  catalog,
  onChange,
  onRemove,
}: {
  condition: SegmentCondition;
  catalog: SegmentFieldsCatalog;
  onChange: (c: SegmentCondition) => void;
  onRemove: () => void;
}) {
  const customerFields = catalog.fields.filter((f) => !PURCHASE_ACTIVITY_KEYS.has(f.key));
  const activityFields = catalog.fields.filter((f) => PURCHASE_ACTIVITY_KEYS.has(f.key));
  const def = fieldDef(catalog.fields, condition.field);
  const operators = catalog.operators_by_type[def.type] ?? [];

  function setField(key: string) {
    const nextDef = fieldDef(catalog.fields, key);
    const nextOps = catalog.operators_by_type[nextDef.type] ?? [];
    onChange(defaultConditionFor(nextDef, nextOps[0]));
  }

  function setOperator(operator: SegmentOperator) {
    onChange({ ...condition, operator, value: def.type === "boolean" ? true : undefined, value2: undefined, values: undefined });
  }

  function renderValueInputs() {
    if (condition.operator === "is_set" || condition.operator === "is_not_set") return null;

    if (condition.operator === "in_list" || condition.operator === "not_in_list") {
      return (
        <input
          aria-label="Values (comma-separated)"
          placeholder="Comma-separated values"
          value={(condition.values ?? []).join(", ")}
          onChange={(e) =>
            onChange({
              ...condition,
              values: e.target.value
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean),
            })
          }
        />
      );
    }

    if (def.type === "enum" && (condition.operator === "equals" || condition.operator === "not_equals")) {
      return (
        <select aria-label="Value" value={(condition.value as string) ?? ""} onChange={(e) => onChange({ ...condition, value: e.target.value })}>
          <option value="" disabled>
            Choose…
          </option>
          {(def.choices ?? []).map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      );
    }

    if (def.type === "boolean") {
      return (
        <select aria-label="Value" value={condition.value === false ? "false" : "true"} onChange={(e) => onChange({ ...condition, value: e.target.value === "true" })}>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      );
    }

    const isDayCount = condition.operator === "within_last_days" || condition.operator === "over_days_ago";
    const inputType = isDayCount ? "number" : def.type === "date" ? "date" : def.type === "number" ? "number" : "text";

    if (condition.operator === "between") {
      return (
        <>
          <input
            aria-label="From"
            type={inputType}
            value={(condition.value as string | number) ?? ""}
            onChange={(e) => onChange({ ...condition, value: inputType === "number" ? Number(e.target.value) : e.target.value })}
          />
          <span className="muted small">and</span>
          <input
            aria-label="To"
            type={inputType}
            value={(condition.value2 as string | number) ?? ""}
            onChange={(e) => onChange({ ...condition, value2: inputType === "number" ? Number(e.target.value) : e.target.value })}
          />
        </>
      );
    }

    return (
      <input
        aria-label="Value"
        type={inputType}
        value={(condition.value as string | number) ?? ""}
        onChange={(e) => onChange({ ...condition, value: inputType === "number" ? Number(e.target.value) : e.target.value })}
      />
    );
  }

  return (
    <div className="segment-condition-row">
      <select aria-label="Field" value={def.key} onChange={(e) => setField(e.target.value)}>
        <optgroup label="Customer fields">
          {customerFields.map((f) => (
            <option key={f.key} value={f.key}>
              {f.label}
            </option>
          ))}
        </optgroup>
        <optgroup label="Purchase activity">
          {activityFields.map((f) => (
            <option key={f.key} value={f.key}>
              {f.label}
            </option>
          ))}
        </optgroup>
        {catalog.custom_fields.length > 0 && (
          <optgroup label="Custom fields">
            {catalog.custom_fields.map((k) => (
              <option key={k} value={`extra.${k}`}>
                {k}
              </option>
            ))}
          </optgroup>
        )}
      </select>

      <select aria-label="Operator" value={condition.operator} onChange={(e) => setOperator(e.target.value as SegmentOperator)}>
        {operators.map((op) => (
          <option key={op} value={op}>
            {OPERATOR_LABELS[op]}
          </option>
        ))}
      </select>

      {renderValueInputs()}

      <button type="button" className="icon-btn btn-ghost" onClick={onRemove} aria-label="Remove condition">
        <Trash2 size={14} />
      </button>
    </div>
  );
}
