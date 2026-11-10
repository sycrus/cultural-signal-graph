/* Who is acting (Workshop B, #52): a name plus a role, remembered per browser and
   shared by both pages (the top bar shows it everywhere). Futures mode sends it with
   every write, so each op in its log records who made it — or, for a model op, who
   asked for it. */

import { signal } from "@preact/signals";

const remembered = (key) => {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
};

export const author = signal(remembered("csg-author") || "strategist");
export const role = signal(remembered("csg-role"));

export function setIdentity(name, r) {
  author.value = (name || "").trim() || "strategist";
  role.value = (r || "").trim();
  try {
    localStorage.setItem("csg-author", author.value);
    localStorage.setItem("csg-role", role.value);
  } catch { /* private window: keep it for this page only */ }
}

export const who = () => ({ author: author.value, role: role.value || null });
