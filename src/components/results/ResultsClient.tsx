"use client";

import { AnimatePresence, motion } from "motion/react";
import { Archive, ArrowLeft, Check, Copy, Download, Palette, X, ZoomIn } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import JSZip from "jszip";

interface ResultsClientProps {
  originalImageUrl: string;
  data: {
    new_img_url: string;
    pbn_url: string;
    colour_names: Record<string, string>;
    rgb_values: Record<string, number[]>;
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────

function triggerDownload(href: string, filename: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(href), 10_000);
}

async function fetchBlob(url: string): Promise<Blob> {
  const res = await fetch(url);
  return res.blob();
}

function buildPaletteText(
  names: Record<string, string>,
  rgbs: Record<string, number[]>,
): string {
  const keys = Object.keys(names).sort((a, b) => +a - +b);
  const header =
    "Paint-by-Numbers — Colour Palette\n" + "=".repeat(38) + "\n\n";
  const lines = keys.map(
    (k) =>
      `${k.padStart(3, " ")}. ${names[k].padEnd(24, " ")}  RGB(${rgbs[k].join(", ")})`,
  );
  return header + lines.join("\n");
}

// ── ImageCard ───────────────────────────────────────────────────────────────

interface ImageCardProps {
  src: string;
  label: string;
  downloadFilename: string;
  onZoom: (src: string) => void;
}

function ImageCard({ src, label, downloadFilename, onZoom }: ImageCardProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      const blob = await fetchBlob(src);
      triggerDownload(URL.createObjectURL(blob), downloadFilename);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <motion.div
      className="group relative bg-card rounded-2xl border border-border overflow-hidden shadow-sm cursor-zoom-in"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.01, boxShadow: "0 8px 32px rgba(0,0,0,0.12)" }}
      transition={{ type: "spring", stiffness: 300, damping: 28 }}
      onClick={() => onZoom(src)}
    >
      {/* Label badge */}
      <div className="absolute top-3 left-3 z-10 bg-black/55 text-white text-xs font-medium px-2.5 py-1 rounded-full backdrop-blur-sm">
        {label}
      </div>

      {/* Zoom hint */}
      <div className="absolute inset-0 z-10 flex-centered opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        <div className="bg-black/40 text-white rounded-full p-2.5 backdrop-blur-sm">
          <ZoomIn size={18} />
        </div>
      </div>

      {/* Download button */}
      <motion.button
        className="absolute top-3 right-3 z-20 bg-black/55 text-white rounded-full p-1.5 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-orange-500 cursor-pointer"
        whileTap={{ scale: 0.9 }}
        onClick={handleDownload}
        disabled={downloading}
        title={`Download ${label}`}
      >
        <Download size={14} />
      </motion.button>

      {/* Image */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={label}
        className="w-full h-full object-contain max-h-[420px]"
        draggable={false}
      />
    </motion.div>
  );
}

// ── Lightbox ────────────────────────────────────────────────────────────────

function Lightbox({
  src,
  onClose,
}: {
  src: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <AnimatePresence>
      {src && (
        <motion.div
          className="fixed inset-0 z-50 flex-centered bg-black/80 backdrop-blur-sm cursor-zoom-out"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
        >
          <motion.div
            className="relative max-w-[90vw] max-h-[90vh]"
            initial={{ scale: 0.85, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.85, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={src}
              alt="Zoomed view"
              className="max-w-[90vw] max-h-[90vh] rounded-xl object-contain shadow-2xl"
              draggable={false}
            />
            <button
              className="absolute -top-3 -right-3 bg-white text-black rounded-full p-1.5 shadow-lg hover:bg-orange-400 hover:text-white transition-colors cursor-pointer"
              onClick={onClose}
              title="Close"
            >
              <X size={16} />
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ── ColourSwatch ─────────────────────────────────────────────────────────────

function ColourSwatch({
  index,
  name,
  rgb,
  delay,
}: {
  index: string;
  name: string;
  rgb: number[];
  delay: number;
}) {
  const [r, g, b] = rgb;
  const cssColour = `rgb(${r}, ${g}, ${b})`;
  const hex = `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
  const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
  const onColour = luminance > 155 ? "rgba(0,0,0,0.7)" : "rgba(255,255,255,0.9)";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(hex);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <motion.div
      className="group relative rounded-2xl overflow-hidden border border-border/50 cursor-pointer select-none"
      initial={{ opacity: 0, y: 20, scale: 0.93 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay, duration: 0.45, ease: [0.23, 1, 0.32, 1] }}
      whileHover={{
        y: -6,
        scale: 1.04,
        boxShadow: `0 16px 40px rgba(${r},${g},${b},0.52)`,
        transition: { type: "spring", stiffness: 340, damping: 22 },
      }}
      style={{
        boxShadow: `0 2px 10px rgba(${r},${g},${b},0.18)`,
      }}
      onClick={handleCopy}
      title={`Click to copy ${hex}`}
    >
      {/* Large colour block */}
      <div
        className="relative h-28 w-full flex items-start justify-between p-2.5"
        style={{ backgroundColor: cssColour }}
      >
        {/* Number badge */}
        <span
          className="text-[11px] font-bold px-2 py-0.5 rounded-lg backdrop-blur-sm"
          style={{ backgroundColor: `rgba(0,0,0,0.18)`, color: onColour }}
        >
          {index}
        </span>

        {/* Hex badge — appears on group hover */}
        <span
          className="text-[10px] font-mono px-1.5 py-0.5 rounded-md backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity duration-200"
          style={{ backgroundColor: `rgba(0,0,0,0.18)`, color: onColour }}
        >
          {hex}
        </span>
      </div>

      {/* Info row */}
      <div className="bg-card px-3 py-2.5 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground capitalize leading-tight truncate">
            {name}
          </p>
          <p className="text-[11px] text-muted-foreground font-mono mt-0.5">
            {r}, {g}, {b}
          </p>
        </div>
        <Copy
          size={13}
          className="shrink-0 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors"
        />
      </div>

      {/* "Copied!" flash overlay */}
      <AnimatePresence>
        {copied && (
          <motion.div
            className="absolute inset-0 flex-centered backdrop-blur-[2px]"
            style={{ backgroundColor: `rgba(${r},${g},${b},0.75)` }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <motion.div
              className="flex items-center gap-1.5 font-semibold text-sm"
              style={{ color: onColour }}
              initial={{ scale: 0.65, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.65, opacity: 0 }}
              transition={{ type: "spring", stiffness: 420, damping: 20 }}
            >
              <Check size={15} />
              Copied!
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function ResultsClient({
  originalImageUrl,
  data,
}: ResultsClientProps) {
  const { new_img_url, pbn_url, colour_names, rgb_values } = data;
  const [zoomedSrc, setZoomedSrc] = useState<string | null>(null);
  const [zipping, setZipping] = useState(false);

  const paletteKeys = Object.keys(colour_names).sort((a, b) => +a - +b);
  const paletteText = buildPaletteText(colour_names, rgb_values);

  const handleZoom = useCallback((src: string) => setZoomedSrc(src), []);
  const handleCloseZoom = useCallback(() => setZoomedSrc(null), []);

  const handleDownloadPalette = () => {
    const blob = new Blob([paletteText], { type: "text/plain" });
    triggerDownload(URL.createObjectURL(blob), "colour-palette.txt");
  };

  const handleDownloadAll = async () => {
    setZipping(true);
    try {
      const zip = new JSZip();
      const [origBlob, processedBlob, canvasBlob] = await Promise.all([
        fetchBlob(originalImageUrl),
        fetchBlob(new_img_url),
        fetchBlob(pbn_url),
      ]);
      zip.file("original.png", origBlob);
      zip.file("processed.png", processedBlob);
      zip.file("canvas.png", canvasBlob);
      zip.file("colour-palette.txt", paletteText);

      const zipBlob = await zip.generateAsync({ type: "blob" });
      triggerDownload(URL.createObjectURL(zipBlob), "paint-by-numbers.zip");
    } finally {
      setZipping(false);
    }
  };

  return (
    <>
      <Lightbox src={zoomedSrc} onClose={handleCloseZoom} />

      <div className="w-full max-w-5xl mx-auto px-4 py-8 space-y-10">
        {/* ── Header ── */}
        <motion.div
          className="flex items-start justify-between gap-4"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors group mt-1"
          >
            <ArrowLeft
              size={15}
              className="group-hover:-translate-x-0.5 transition-transform"
            />
            Back to Home
          </Link>

          <div className="text-center flex-1">
            <h1
              className="text-3xl sm:text-4xl font-paint"
              style={{ color: "#973f29" }}
            >
              Your Generated Canvas
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Click any image to zoom · hover to download
            </p>
          </div>

          {/* Spacer to balance the back button */}
          <div className="w-24 shrink-0" />
        </motion.div>

        {/* ── Top Row: Original + Processed ── */}
        <motion.section
          className="space-y-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15 }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <ImageCard
              src={originalImageUrl}
              label="Original"
              downloadFilename="original.png"
              onZoom={handleZoom}
            />
            <ImageCard
              src={new_img_url}
              label="Processed"
              downloadFilename="processed.png"
              onZoom={handleZoom}
            />
          </div>
        </motion.section>

        {/* ── PBN Canvas (full width) ── */}
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <ImageCard
            src={pbn_url}
            label="Paint-by-Numbers Canvas"
            downloadFilename="canvas.png"
            onZoom={handleZoom}
          />
        </motion.section>

        {/* ── Colour Palette ── */}
        <motion.section
          className="space-y-5"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
        >
          {/* Palette header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Palette size={18} className="text-orange-500" />
              <h2 className="text-lg font-semibold text-foreground">
                Colour Palette
              </h2>
              <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                {paletteKeys.length} colours
              </span>
            </div>
            <motion.button
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-orange-500 transition-colors cursor-pointer"
              whileHover={{ x: 1 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleDownloadPalette}
              title="Download colour list as .txt"
            >
              <Download size={14} />
              Download .txt
            </motion.button>
          </div>

          {/* Colour strip */}
          <motion.div
            className="h-7 rounded-xl overflow-hidden flex shadow-sm"
            initial={{ opacity: 0, scaleX: 0.8 }}
            animate={{ opacity: 1, scaleX: 1 }}
            transition={{ delay: 0.4, duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
            title="All palette colours"
            aria-hidden
          >
            {paletteKeys.map((key) => {
              const [r, g, b] = rgb_values[key];
              return (
                <div
                  key={key}
                  className="flex-1 h-full transition-transform hover:scale-y-110 origin-bottom"
                  style={{ backgroundColor: `rgb(${r},${g},${b})` }}
                  title={colour_names[key]}
                />
              );
            })}
          </motion.div>

          {/* Swatches grid — click any card to copy its hex */}
          <p className="text-xs text-muted-foreground -mt-1">
            Click a swatch to copy its hex value
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {paletteKeys.map((key, i) => (
              <ColourSwatch
                key={key}
                index={key}
                name={colour_names[key]}
                rgb={rgb_values[key]}
                delay={0.42 + i * 0.03}
              />
            ))}
          </div>
        </motion.section>

        {/* ── Download All ZIP ── */}
        <motion.div
          className="pt-2 pb-6"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <motion.button
            className="w-full flex-centered gap-3 py-4 rounded-2xl bg-orange-400 hover:bg-accent-main text-white font-semibold text-base shadow-md cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            whileHover={
              zipping
                ? {}
                : { scale: 1.01, boxShadow: "0 6px 24px rgba(249,115,22,0.35)" }
            }
            whileTap={zipping ? {} : { scale: 0.99 }}
            onClick={handleDownloadAll}
            disabled={zipping}
          >
            {zipping ? (
              <>
                <motion.div
                  className="w-5 h-5 border-2 border-white/40 border-t-white rounded-full"
                  animate={{ rotate: 360 }}
                  transition={{
                    duration: 0.8,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                />
                Preparing your download…
              </>
            ) : (
              <>
                <Archive size={20} />
                Download Everything as ZIP
              </>
            )}
          </motion.button>
        </motion.div>
      </div>
    </>
  );
}
