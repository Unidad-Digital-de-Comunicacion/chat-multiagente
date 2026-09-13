import type { ReactNode } from "react";

export default function Modal({
  title,
  onClose,
  children,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={"modal-card" + (wide ? " modal-card-wide" : "")} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Cerrar">
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
