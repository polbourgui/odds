import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  formatFreshness,
  formatKickoff,
  formatMarket,
  formatOdds,
  formatPct,
  formatSelection,
  formatStake,
} from "../format";
import type { ValueBet } from "../types";
import { PlaceBetButton } from "./PlaceBetButton";
import styles from "./ValueBetsTable.module.css";

const columnHelper = createColumnHelper<ValueBet>();

const columns = [
  columnHelper.accessor("start_time", {
    header: "Coup d'envoi",
    cell: (info) => formatKickoff(info.getValue()),
  }),
  columnHelper.accessor("competition_name", {
    header: "Compétition",
  }),
  columnHelper.display({
    id: "event",
    header: "Événement",
    cell: (info) => (
      <Link className={styles.eventLink} to={`/events/${info.row.original.event_id}`}>
        {info.row.original.home_name} – {info.row.original.away_name}
      </Link>
    ),
  }),
  columnHelper.display({
    id: "market",
    header: "Marché",
    cell: (info) => formatMarket(info.row.original.market_type, info.row.original.line),
  }),
  columnHelper.display({
    id: "selection",
    header: "Sélection",
    cell: (info) =>
      formatSelection(info.row.original.selection_code, info.row.original.participant_name),
  }),
  columnHelper.accessor("bookmaker_name", {
    header: "Book",
  }),
  columnHelper.accessor("book_odds", {
    header: "Cote book",
    cell: (info) => <span className="num">{formatOdds(info.getValue())}</span>,
  }),
  columnHelper.accessor("fair_odds", {
    header: "Cote juste",
    cell: (info) => <span className="num">{formatOdds(info.getValue())}</span>,
  }),
  columnHelper.accessor("edge", {
    header: "Edge",
    cell: (info) => {
      const value = info.getValue();
      return (
        <span className={`num ${value >= 0 ? "positive" : "negative"}`}>
          {formatPct(value)}
        </span>
      );
    },
  }),
  columnHelper.accessor("kelly_stake", {
    header: "Mise Kelly",
    cell: (info) => <span className="num">{formatStake(info.getValue())}</span>,
  }),
  columnHelper.accessor("captured_at", {
    header: "Fraîcheur",
    cell: (info) => <span className="num">{formatFreshness(info.getValue())}</span>,
  }),
  columnHelper.display({
    id: "place_bet",
    header: "",
    cell: (info) => (
      <PlaceBetButton
        selectionId={info.row.original.selection_id}
        bookmakerSlug={info.row.original.bookmaker_slug}
      />
    ),
  }),
];

interface ValueBetsTableProps {
  data: ValueBet[];
}

export function ValueBetsTable({ data }: ValueBetsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "edge", desc: true }]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (data.length === 0) {
    return <div className={styles.empty}>Aucun value bet ne correspond aux filtres actuels.</div>;
  }

  return (
    <div className={styles.wrapper}>
      <table className={styles.table}>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id} onClick={header.column.getToggleSortingHandler()}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  <span className={styles.sortIndicator}>
                    {{ asc: "▲", desc: "▼" }[header.column.getIsSorted() as string] ?? ""}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
