import type { ScanResponse, ScoreRecord, SearchResponse } from "./types";

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
  openTab: (tab: "overall" | "card" | "ovr" | "scan" | "validate" | "method") => void;
};

export type TerminalContext = TerminalSessionState & TerminalSessionActions;
