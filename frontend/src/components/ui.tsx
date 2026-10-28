import React, { useEffect, useId, useRef } from "react";

type ButtonVariant = "primary" | "secondary" | "quiet" | "danger";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  loading = false,
  disabled,
  className = "",
  children,
  ...props
}) => (
  <button
    {...props}
    className={`ui-button ui-button--${variant} ${className}`.trim()}
    disabled={disabled || loading}
    aria-busy={loading || undefined}
  >
    {loading && <span className="ui-spinner" aria-hidden="true" />}
    {children}
  </button>
);

export const Card: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className = "", ...props }) => (
  <div {...props} className={`ui-card ${className}`.trim()} />
);

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

export const Badge: React.FC<React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }> = ({
  tone = "neutral",
  className = "",
  ...props
}) => <span {...props} className={`ui-badge ui-badge--${tone} ${className}`.trim()} />;

interface FieldProps {
  label?: React.ReactNode;
  description?: React.ReactNode;
  className?: string;
}

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & FieldProps;

export const Input: React.FC<InputProps> = ({ label, description, className = "", id, ...props }) => {
  const generatedId = useId();
  const inputId = id || generatedId;
  const descriptionId = description ? `${inputId}-description` : undefined;
  const input = <input {...props} id={inputId} aria-describedby={descriptionId || props["aria-describedby"]} className={className} />;
  return label ? (
    <label className="ui-field" htmlFor={inputId}>
      <span>{label}</span>
      {input}
      {description && <span id={descriptionId} className="text-sm text-secondary">{description}</span>}
    </label>
  ) : input;
};

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & FieldProps;

export const Select: React.FC<SelectProps> = ({ label, description, className = "", id, children, ...props }) => {
  const generatedId = useId();
  const selectId = id || generatedId;
  const descriptionId = description ? `${selectId}-description` : undefined;
  const select = <select {...props} id={selectId} aria-describedby={descriptionId || props["aria-describedby"]} className={className}>{children}</select>;
  return label ? (
    <label className="ui-field" htmlFor={selectId}>
      <span>{label}</span>
      {select}
      {description && <span id={descriptionId} className="text-sm text-secondary">{description}</span>}
    </label>
  ) : select;
};

export interface TabItem {
  id: string;
  label: React.ReactNode;
  disabled?: boolean;
}

export const Tabs: React.FC<{
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  label: string;
  className?: string;
}> = ({ items, value, onChange, label, className = "" }) => {
  const activateByOffset = (index: number, offset: number) => {
    for (let step = 1; step <= items.length; step += 1) {
      const candidate = items[(index + offset * step + items.length) % items.length];
      if (!candidate.disabled) {
        onChange(candidate.id);
        requestAnimationFrame(() => document.getElementById(`ui-tab-${candidate.id}`)?.focus());
        return;
      }
    }
  };
  return (
    <div className={`ui-tabs ${className}`.trim()} role="tablist" aria-label={label}>
      {items.map((item, index) => (
        <button
          key={item.id}
          id={`ui-tab-${item.id}`}
          type="button"
          role="tab"
          className="ui-tab"
          aria-selected={value === item.id}
          aria-controls={`ui-panel-${item.id}`}
          tabIndex={value === item.id ? 0 : -1}
          disabled={item.disabled}
          onClick={() => onChange(item.id)}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight") { event.preventDefault(); activateByOffset(index, 1); }
            if (event.key === "ArrowLeft") { event.preventDefault(); activateByOffset(index, -1); }
            if (event.key === "Home") { event.preventDefault(); activateByOffset(-1, 1); }
            if (event.key === "End") { event.preventDefault(); activateByOffset(0, -1); }
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
};

export const Table: React.FC<React.TableHTMLAttributes<HTMLTableElement>> = ({ className = "", ...props }) => (
  <div className="ui-table-wrap"><table {...props} className={`ui-table ${className}`.trim()} /></div>
);

interface ModalProps {
  open: boolean;
  title: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
  drawer?: boolean;
}

export const Modal: React.FC<ModalProps> = ({ open, title, onClose, children, className = "", drawer = false }) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={dialogRef}
      className={`ui-dialog ${drawer ? "ui-drawer" : ""} ${className}`.trim()}
      aria-labelledby={titleId}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClose={() => { if (open) onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <header className="mb-5 flex items-start justify-between gap-4">
        <h2 id={titleId} className="text-xl font-semibold text-primary">{title}</h2>
        <button type="button" className="min-h-11 min-w-11 rounded-pill text-secondary" aria-label="Close dialog" onClick={onClose}>×</button>
      </header>
      {children}
    </dialog>
  );
};

export const EmptyState: React.FC<{
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}> = ({ title, description, action, className = "" }) => (
  <div className={`ui-empty-state ${className}`.trim()}>
    <svg aria-hidden="true" width="44" height="44" viewBox="0 0 44 44" fill="none">
      <path d="M22 4 7.5 10v10.2c0 9.3 6.2 17.4 14.5 20 8.3-2.6 14.5-10.7 14.5-20V10L22 4Z" stroke="currentColor" strokeWidth="1.8" />
      <path d="m16 21.5 4 4 8.5-9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
    <h2 className="text-base font-semibold text-primary">{title}</h2>
    {description && <p className="max-w-lg text-sm">{description}</p>}
    {action}
  </div>
);

export const Stat: React.FC<{ label: string; value: React.ReactNode; detail?: React.ReactNode; className?: string }> = ({
  label, value, detail, className = "",
}) => (
  <div className={`ui-card ui-stat ${className}`.trim()}>
    <p className="ui-stat__label">{label}</p>
    <p className="ui-stat__value">{value}</p>
    {detail && <p className="mt-1 text-sm text-secondary">{detail}</p>}
  </div>
);

export const Stepper: React.FC<{ steps: string[]; current: number; className?: string }> = ({ steps, current, className = "" }) => (
  <ol className={`ui-stepper ${className}`.trim()} aria-label="Submission progress">
    {steps.map((step, index) => (
      <li key={step} className="ui-stepper__step" data-complete={index < current} data-current={index === current} aria-current={index === current ? "step" : undefined}>
        <span className="ui-stepper__dot" aria-hidden="true" />
        <span className="text-xs">{step}</span>
      </li>
    ))}
  </ol>
);

export const Tooltip: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => {
  const descriptionId = useId();
  const accessibleChild = React.isValidElement(children) && children.type !== React.Fragment
    ? React.cloneElement(children as React.ReactElement<{ "aria-describedby"?: string }>, { "aria-describedby": descriptionId })
    : children;
  return (
    <span className="ui-tooltip" data-tooltip={label}>
      <span id={descriptionId} role="tooltip" className="sr-only">{label}</span>
      {accessibleChild}
    </span>
  );
};

export const Toast: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className = "", ...props }) => (
  <div {...props} className={`ui-toast ${className}`.trim()} />
);
