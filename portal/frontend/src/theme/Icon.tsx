/* Line icons of the portal mockup (24×24, stroke = currentColor). Static markup only. */
const paths = {
  home: "<path d=\"M3 11l9-7 9 7\"/><path d=\"M5 10v10h5v-6h4v6h5V10\"/>",
  planet: "<circle cx=\"12\" cy=\"12\" r=\"6.5\"/><ellipse cx=\"12\" cy=\"12\" rx=\"11\" ry=\"4\" transform=\"rotate(-24 12 12)\"/>",
  layers: "<path d=\"M12 3l9 5-9 5-9-5z\"/><path d=\"M3 13l9 5 9-5\"/><path d=\"M3 17.5l9 5 9-5\" opacity=\".6\"/>",
  users: "<circle cx=\"9\" cy=\"8\" r=\"3.2\"/><path d=\"M3 20c0-3.6 2.7-6 6-6s6 2.4 6 6\"/><circle cx=\"17.5\" cy=\"9\" r=\"2.5\"/><path d=\"M16 14.3c3 .1 5 2.2 5 5.7\"/>",
  news: "<rect x=\"3\" y=\"4\" width=\"15\" height=\"16\" rx=\"2\"/><path d=\"M18 8h3v10a2 2 0 0 1-2 2\"/><path d=\"M7 8h7M7 12h7M7 16h4\"/>",
  user: "<circle cx=\"12\" cy=\"8\" r=\"4\"/><path d=\"M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7\"/>",
  userplus: "<circle cx=\"10\" cy=\"8\" r=\"4\"/><path d=\"M2 21c0-4.4 3.6-7 8-7 1.9 0 3.6.5 5 1.4\"/><path d=\"M19 13v7M15.5 16.5h7\"/>",
  arrow: "<path d=\"M4 12h15M13 6l6 6-6 6\"/>",
  mail: "<rect x=\"3\" y=\"5\" width=\"18\" height=\"14\" rx=\"2\"/><path d=\"M3.5 6.5L12 13l8.5-6.5\"/>",
  lock: "<rect x=\"4.5\" y=\"10.5\" width=\"15\" height=\"10\" rx=\"2\"/><path d=\"M8 10.5V8a4 4 0 0 1 8 0v2.5\"/>",
  gamepad: "<path d=\"M7 7h10a5 5 0 0 1 4.8 6.3l-1 3.6a2.6 2.6 0 0 1-4.5 1L14.5 16h-5l-1.8 1.9a2.6 2.6 0 0 1-4.5-1l-1-3.6A5 5 0 0 1 7 7z\"/><path d=\"M7.5 10v4M5.5 12h4\"/><circle cx=\"16\" cy=\"11\" r=\".8\" fill=\"currentColor\"/><circle cx=\"18\" cy=\"13\" r=\".8\" fill=\"currentColor\"/>",
  check: "<path d=\"M5 12.5l4.5 4.5L19 7.5\"/>",
  x: "<path d=\"M6 6l12 12M18 6L6 18\"/>",
  play: "<path d=\"M7 4.5v15l12-7.5z\"/>",
  chevdown: "<path d=\"M6 9l6 6 6-6\"/>",
  bell: "<path d=\"M6 16V11a6 6 0 0 1 12 0v5l2 2H4z\"/><path d=\"M10 20a2 2 0 0 0 4 0\"/>",
  flag: "<path d=\"M5 21V4\"/><path d=\"M5 4h12l-2.5 4L17 12H5\"/>",
  clock: "<circle cx=\"12\" cy=\"12\" r=\"8.5\"/><path d=\"M12 7.5V12l3 2\"/>",
  chart: "<path d=\"M5 20V12M10 20V6M15 20v-9M20 20V4\"/>",
  compass: "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21\"/><path d=\"M12 7l2 5-2 5-2-5z\" fill=\"currentColor\" fill-opacity=\".25\"/>",
  dome: "<path d=\"M3 20h18\"/><path d=\"M5 20v-3a7 7 0 0 1 14 0v3\"/><path d=\"M12 10V6M10 6h4M8 13.5h8\"/>",
  handshake: "<path d=\"M2 11l4-4 4 2 3-2 3 1 4 3\"/><path d=\"M6 13l4 4a1.5 1.5 0 0 0 2-2\"/><path d=\"M9 16l2 2a1.5 1.5 0 0 0 2-2l-2-2\"/><path d=\"M12 17l1 1a1.5 1.5 0 0 0 2-2l-3-3\"/><path d=\"M16 15l1 1a1.5 1.5 0 0 0 2-2l-3-4\"/>",
  rocket: "<path d=\"M14 4c3-1.5 5.5-1 6-1-0 .5.5 3-1 6l-6 6-4-4z\"/><path d=\"M9 11l-4 .5-2 2.5 4 1M13 15l-.5 4-2.5 2-1-4\"/><circle cx=\"15.5\" cy=\"8.5\" r=\"1.4\"/><path d=\"M6 18l-2 2\"/>",
  flask: "<path d=\"M9 3h6M10 3v6l-5.5 9.5A1.8 1.8 0 0 0 6 21h12a1.8 1.8 0 0 0 1.5-2.5L14 9V3\"/><path d=\"M7 15h10\"/>",
  shield: "<path d=\"M12 3l8 3v6c0 5-3.6 8-8 9-4.4-1-8-4-8-9V6z\"/><path d=\"M12 8.5l1.2 2.4 2.6.3-1.9 1.8.5 2.6L12 14.3l-2.4 1.3.5-2.6-1.9-1.8 2.6-.3z\" fill=\"currentColor\" fill-opacity=\".3\"/>",
  infinity: "<path d=\"M7.5 8.5c-2 0-3.5 1.6-3.5 3.5s1.5 3.5 3.5 3.5c3.5 0 5.5-7 9-7 2 0 3.5 1.6 3.5 3.5s-1.5 3.5-3.5 3.5c-3.5 0-5.5-7-9-7z\"/>",
  bolt: "<path d=\"M13 2L4 14h7l-1 8 9-12h-7z\"/>",
  trophy: "<path d=\"M8 4h8v5a4 4 0 0 1-8 0z\"/><path d=\"M8 6H4.5a3 3 0 0 0 3.5 4M16 6h3.5a3 3 0 0 1-3.5 4M12 13v4M8 21h8M9.5 17h5\"/>",
  calendar: "<rect x=\"3.5\" y=\"5\" width=\"17\" height=\"15\" rx=\"2\"/><path d=\"M3.5 10h17M8 3v4M16 3v4\"/>",
  spiral: "<path d=\"M12 12a1.5 1.5 0 1 1 1.5-1.5A4 4 0 1 1 9 15a6.5 6.5 0 1 1 9.5-7\"/><path d=\"M12 12a6 6 0 0 0-8 2\"/>",
  menu: "<path d=\"M4 7h16M4 12h16M4 17h16\"/>",
  plus: "<path d=\"M12 5v14M5 12h14\"/>",
  map: "<path d=\"M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z\"/><path d=\"M9 4v14M15 6v14\"/>",
  globe: "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M3 12h18M12 3c2.5 2.6 3.7 5.6 3.7 9s-1.2 6.4-3.7 9c-2.5-2.6-3.7-5.6-3.7-9S9.5 5.6 12 3z\"/>",
  laurel: "<path d=\"M12 21c-5-1-8-5-8-11\"/><path d=\"M12 21c5-1 8-5 8-11\"/><path d=\"M5 13c-1.5-.5-2.5-2-2.5-3.5 1.5 0 3 1 3.5 2.5M6.5 16.5c-1.5 0-3-1-3.5-2.5 1.5-.3 3 .3 4 1.5M5 9.5C4 8.5 4 7 4.5 6c1 .6 1.7 2 1.5 3.3M19 13c1.5-.5 2.5-2 2.5-3.5-1.5 0-3 1-3.5 2.5M17.5 16.5c1.5 0 3-1 3.5-2.5-1.5-.3-3 .3-4 1.5M19 9.5c1-1 1-2.5.5-3.5-1 .6-1.7 2-1.5 3.3\"/>",
  orbit: "<circle cx=\"12\" cy=\"12\" r=\"3.5\"/><ellipse cx=\"12\" cy=\"12\" rx=\"10\" ry=\"4.5\"/><ellipse cx=\"12\" cy=\"12\" rx=\"10\" ry=\"4.5\" transform=\"rotate(60 12 12)\"/>",
  logout: "<path d=\"M10 4H5v16h5\"/><path d=\"M14 8l4 4-4 4M18 12H9\"/>",
  settings: "<circle cx=\"12\" cy=\"12\" r=\"3\"/><path d=\"M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1\"/>",
} as const;

export type IconName = keyof typeof paths;

/** Decorative icon: the accessible name always comes from the surrounding text. */
export function Icon({ name, className = "p-i" }: { name: IconName; className?: string }) {
  return <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false" dangerouslySetInnerHTML={{ __html: paths[name] }} />;
}
