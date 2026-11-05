import { useEffect, useRef, useState } from "react";
import type { VoterFields } from "./api";

export function categoryFor(fields: VoterFields | null, caste: string): string | null {
  if (!caste) return null;
  return fields?.castes.find((item) => item.name === caste)?.category ?? null;
}

export function leaderFor(fields: VoterFields | null, ideology: string): string | null {
  if (!ideology) return null;
  return fields?.ideologies.find((item) => item.name === ideology)?.leader ?? null;
}

export function Choice({
  label,
  value,
  options,
  onChange,
  disabled,
  compact,
  empty,
}: {
  label: string;
  value: string | null;
  options: string[];
  onChange: (value: string) => void;
  disabled?: boolean;
  compact?: boolean;
  empty: string;
}) {
  const [editing, setEditing] = useState(false);
  if (compact && !editing) {
    return (
      <button
        type="button"
        className="cell-select"
        aria-label={label}
        disabled={disabled || options.length === 0}
        onClick={() => setEditing(true)}
      >
        {value || empty}
      </button>
    );
  }
  const select = (
    <select
      className={compact ? "cell-select" : undefined}
      aria-label={label}
      value={value ?? ""}
      disabled={disabled || options.length === 0}
      autoFocus={compact}
      onBlur={() => {
        if (compact) window.setTimeout(() => setEditing(false), 150);
      }}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">{empty}</option>
      {options.map((item) => (
        <option key={item} value={item}>
          {item}
        </option>
      ))}
    </select>
  );
  if (compact) return select;
  return (
    <label className="field">
      {label}
      {select}
    </label>
  );
}

export function KindEditor({
  options,
  selected,
  onChange,
  disabled,
}: {
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  disabled?: boolean;
}) {
  return (
    <div className="pick-list">
      {options.map((item) => (
        <label key={item}>
          <input
            type="checkbox"
            checked={selected.includes(item)}
            disabled={disabled}
            onChange={() => {
              const next = selected.includes(item) ? selected.filter((kind) => kind !== item) : [...selected, item];
              onChange(next);
            }}
          />
          <span>{item}</span>
        </label>
      ))}
    </div>
  );
}

export function NoteInput({
  label,
  value,
  onSave,
  disabled,
  compact,
}: {
  label: string;
  value: string;
  onSave: (value: string) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  const [text, setText] = useState(value);
  const saved = useRef(value);
  const onSaveRef = useRef(onSave);
  onSaveRef.current = onSave;
  useEffect(() => {
    if (value === saved.current) return;
    setText(value);
    saved.current = value;
  }, [value]);
  useEffect(() => {
    if (text === saved.current) return;
    const timer = window.setTimeout(() => {
      saved.current = text;
      onSaveRef.current(text);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [text]);

  const input = (
    <input
      className={compact ? "note-line" : undefined}
      aria-label={label}
      value={text}
      disabled={disabled}
      placeholder={label}
      onChange={(event) => setText(event.target.value)}
    />
  );
  if (compact) return input;
  return (
    <label className="field">
      {label}
      {input}
    </label>
  );
}
