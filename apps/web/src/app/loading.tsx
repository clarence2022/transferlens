export default function Loading() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-8 h-8 border-2 border-bloomberg-orange/30 border-t-bloomberg-orange rounded-full animate-spin" />
        <span className="text-text-secondary text-sm">Loading...</span>
      </div>
    </div>
  );
}
