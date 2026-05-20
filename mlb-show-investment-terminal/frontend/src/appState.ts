import type { ScanResponse, ScoreRecord, SearchResponse } from "./types";

export type TerminalTab =
  | "command"
  | "scanner"
  | "target"
  | "matrix"
  | "forecast"
  | "validation"
  | "ledger"
  | "risk"
  | "audit"
  | "ops";

export type TerminalSessionState = {
  loadedUuids: string[];
  currentRecord?: ScoreRecord;
  lastSearch?: SearchResponse;
  lastSearchAt?: string;
  lastListingAt?: string;
  lastScan?: ScanResponse;
  lastScanAt?: string;
  apiOkAt?: string;
  apiErrAt?: string;
};

export type TerminalSessionActions = {
  addLoadedUuid: (uuid: string) => void;
  setCurrentRecord: (record: ScoreRecord) => void;
  setLastSearch: (payload: SearchResponse) => void;
  setLastScan: (payload: ScanResponse) => void;
  markApiOk: () => void;
  markApiErr: () => void;
  openTab: (tab: TerminalTab) => void;
};

export type TerminalContext = TerminalSessionState & TerminalSessionActions;
