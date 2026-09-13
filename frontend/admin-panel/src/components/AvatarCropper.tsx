import { type PointerEvent, useEffect, useRef, useState } from "react";

import Modal from "./Modal";

const FRAME = 240;
// Se exporta a un canvas más grande que el frame visible para no perder
// nitidez en pantallas de alta densidad — se ve chico en la UI pero el
// archivo final tiene buena resolución.
const OUTPUT = 480;

/** Editor de avatar sin dependencias externas: el usuario arrastra la foto
 * para centrarla y usa el control de zoom para acercarla o alejarla dentro
 * de un marco circular fijo; al confirmar, se recorta a un cuadrado con
 * <canvas> y se sube ya recortado (el back sólo tiene que generar la
 * miniatura con Pillow, no volver a recortar). */
export default function AvatarCropper({
  file, onCancel, onConfirm,
}: {
  file: File;
  onCancel: () => void;
  onConfirm: (blob: Blob) => void;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const dragOrigin = useRef<{ x: number; y: number } | null>(null);

  // La URL se crea Y se revoca dentro del mismo efecto (no en un useState
  // inicial con revoke en un efecto aparte) porque en React 18 + StrictMode
  // el modo desarrollo monta cada efecto dos veces (monta → limpia → vuelve
  // a montar) para detectar fugas — si el revoke queda en un efecto propio
  // separado de dónde se creó la URL, esa primera pasada revoca la URL
  // antes de que la imagen llegue a cargarla, y la foto nunca aparece.
  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const baseScale = natural.w && natural.h ? Math.max(FRAME / natural.w, FRAME / natural.h) : 1;
  const scale = baseScale * zoom;
  const dispW = natural.w * scale;
  const dispH = natural.h * scale;
  const maxOffsetX = Math.max(0, (dispW - FRAME) / 2);
  const maxOffsetY = Math.max(0, (dispH - FRAME) / 2);

  function clampFor(z: number, o: { x: number; y: number }) {
    const s = baseScale * z;
    const maxX = Math.max(0, (natural.w * s - FRAME) / 2);
    const maxY = Math.max(0, (natural.h * s - FRAME) / 2);
    return {
      x: Math.min(maxX, Math.max(-maxX, o.x)),
      y: Math.min(maxY, Math.max(-maxY, o.y)),
    };
  }

  function clamp(o: { x: number; y: number }) {
    return clampFor(zoom, o);
  }

  function handleImgLoad() {
    const img = imgRef.current;
    if (!img) return;
    setNatural({ w: img.naturalWidth, h: img.naturalHeight });
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }

  function handlePointerDown(e: PointerEvent<HTMLDivElement>) {
    (e.target as Element).setPointerCapture(e.pointerId);
    dragOrigin.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
  }

  function handlePointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!dragOrigin.current) return;
    setOffset(clamp({ x: e.clientX - dragOrigin.current.x, y: e.clientY - dragOrigin.current.y }));
  }

  function handlePointerUp() {
    dragOrigin.current = null;
  }

  function handleZoom(z: number) {
    setZoom(z);
    setOffset((prev) => clampFor(z, prev));
  }

  function confirmar() {
    const img = imgRef.current;
    if (!img || !src) return;
    const canvas = document.createElement("canvas");
    canvas.width = OUTPUT;
    canvas.height = OUTPUT;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const factor = OUTPUT / FRAME;
    const drawW = dispW * factor;
    const drawH = dispH * factor;
    const drawX = OUTPUT / 2 - drawW / 2 + offset.x * factor;
    const drawY = OUTPUT / 2 - drawH / 2 + offset.y * factor;
    ctx.drawImage(img, drawX, drawY, drawW, drawH);
    canvas.toBlob((blob) => {
      if (blob) onConfirm(blob);
    }, "image/jpeg", 0.9);
  }

  return (
    <Modal title="Ajustar foto de perfil" onClose={onCancel}>
      <div className="cropper">
        <div
          className="cropper-frame"
          style={{ width: FRAME, height: FRAME }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
        >
          {src && (
            <img
              ref={imgRef}
              src={src}
              alt=""
              draggable={false}
              onLoad={handleImgLoad}
              style={{
                width: dispW || undefined,
                height: dispH || undefined,
                transform: `translate(calc(-50% + ${offset.x}px), calc(-50% + ${offset.y}px))`,
              }}
            />
          )}
        </div>
        <label className="cropper-zoom">
          Zoom
          <input
            type="range"
            min={1}
            max={3}
            step={0.05}
            value={zoom}
            onChange={(e) => handleZoom(Number(e.target.value))}
          />
        </label>
        <p className="text-muted field-help">
          Arrastrá la foto para centrarla y usá el control para acercar o alejar.
        </p>
        <div className="toolbar">
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" className="btn btn-primary" onClick={confirmar}>
            Usar esta foto
          </button>
        </div>
      </div>
    </Modal>
  );
}
