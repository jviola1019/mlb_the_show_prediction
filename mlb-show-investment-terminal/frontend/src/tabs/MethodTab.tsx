import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { Panel, Pill } from "../components";

export function MethodTab() {
  const parity = useQuery({ queryKey: ["parity-audit"], queryFn: api.parity });
  return (
    <div className="grid">
      <Panel title="Architecture">
        <p>React renders the terminal. FastAPI serves `/api` and the static React build from the same origin. Python owns every quant decision and reproducible CLI command.</p>
      </Panel>
      <Panel title="Engine Contracts">
        <pre>{`flip.after_tax_sale = ask * 0.90
flip.profit = after_tax_sale - bid
flip.roi = profit / bid

upgrade = threshold-crossing probability
forecast = diagnostic-only price-history bootstrap
cv/ic gates = forecast diagnostics only`}</pre>
      </Panel>
      <Panel title="Deployment">
        <p>Render and Hugging Face use one Docker image. Runtime storage is ephemeral; historical labels are committed artifacts, not written by the hosted app.</p>
      </Panel>
      <Panel title="Parity Audit" kicker={parity.data?.generated_at ?? "checking"}>
        <div className="status-line">
          <Pill tone={parity.data?.status === "ok" ? "good" : "warn"}>{parity.data?.status ?? "loading"}</Pill>
          <Pill>parity {parity.data?.counts?.parity ?? 0}</Pill>
          <Pill tone="warn">partial {parity.data?.counts?.partial ?? 0}</Pill>
          <Pill tone="bad">missing {parity.data?.counts?.missing ?? 0}</Pill>
        </div>
        <div className="table-wrap mini-table">
          <table>
            <thead><tr><th>Feature</th><th>Group</th><th>Status</th></tr></thead>
            <tbody>
              {(parity.data?.features ?? []).map((row) => (
                <tr key={String(row.feature_id)}>
                  <td><code>{String(row.feature_id)}</code></td>
                  <td>{String(row.group)}</td>
                  <td>{String(row.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
