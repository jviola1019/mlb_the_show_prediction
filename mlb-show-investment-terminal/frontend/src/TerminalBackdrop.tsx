export default function TerminalBackdrop() {
  return (
    <div className="terminal-backdrop" aria-hidden="true" data-testid="terminal-backdrop">
      <div className="terminal-grid-plane" />
      <div className="terminal-signal-lines" />
    </div>
  );
}
