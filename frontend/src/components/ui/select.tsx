import * as React from "react";
import { Check, ChevronDown, X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  count?: number;
}

interface SelectProps extends React.HTMLAttributes<HTMLDivElement> {
  options: SelectOption[];
  value?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  clearable?: boolean;
}

/** Lightweight multi/single select built on native semantics but custom UI. */
export function Select({
  options,
  value,
  onValueChange,
  placeholder = "Select…",
  clearable = false,
  className,
  ...props
}: SelectProps) {
  const [open, setOpen] = React.useState(false);
  const selected = options.find((o) => o.value === value);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div ref={ref} className={cn("relative", className)} {...props}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex h-10 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 py-2 text-sm transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className={cn("truncate", !selected && "text-muted-foreground")}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
      </button>
      {open ? (
        <div className="absolute z-50 mt-1 max-h-72 w-full min-w-[12rem] overflow-auto rounded-lg border border-border bg-popover p-1 shadow-lg">
          {clearable && value ? (
            <button
              type="button"
              onClick={() => {
                onValueChange?.("");
                setOpen(false);
              }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent"
            >
              <X className="size-3.5" /> Clear
            </button>
          ) : null}
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                onValueChange?.(option.value);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent",
                option.value === value && "font-medium text-primary",
              )}
            >
              <span className="truncate">{option.label}</span>
              <span className="flex items-center gap-1">
                {typeof option.count === "number" && (
                  <span className="text-xs text-muted-foreground">{option.count}</span>
                )}
                {option.value === value && <Check className="size-3.5" />}
              </span>
            </button>
          ))}
          {options.length === 0 ? (
            <p className="px-2 py-3 text-center text-xs text-muted-foreground">No options</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export interface MultiSelectProps extends SelectProps {
  values: string[];
  onValuesChange?: (values: string[]) => void;
  max?: number;
}

export function MultiSelect({
  options,
  values,
  onValuesChange,
  placeholder = "Select…",
  max = 8,
  className,
}: MultiSelectProps) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const toggle = (value: string) => {
    if (values.includes(value)) {
      onValuesChange?.(values.filter((v) => v !== value));
    } else if (values.length < max) {
      onValuesChange?.([...values, value]);
    }
  };

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-10 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 py-2 text-sm transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className={cn("truncate", values.length === 0 && "text-muted-foreground")}>
          {values.length === 0 ? placeholder : `${values.length} selected`}
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
      </button>
      {open ? (
        <div className="absolute z-50 mt-1 max-h-72 w-full min-w-[14rem] overflow-auto rounded-lg border border-border bg-popover p-1 shadow-lg">
          {options.map((option) => {
            const active = values.includes(option.value);
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => toggle(option.value)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent",
                  active && "font-medium text-primary",
                )}
              >
                <span className="truncate">{option.label}</span>
                <span className="flex items-center gap-1">
                  {typeof option.count === "number" && (
                    <span className="text-xs text-muted-foreground">{option.count}</span>
                  )}
                  {active && <Check className="size-3.5" />}
                </span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
