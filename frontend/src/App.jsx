import { useState } from "react";
import Navbar      from "./components/Navbar";
import HomePage    from "./pages/HomePage";
import PlayerPage  from "./pages/PlayerPage";
import ExplorePage from "./pages/ExplorePage";
import { usePlayersList } from "./hooks/usePlayersList";

export default function App() {
  const [view,          setView]          = useState("home");
  const [player,        setPlayer]        = useState(null);
  const [playerLeague,  setPlayerLeague]  = useState("Ligue_1");
  const [exploreLeague, setExploreLeague] = useState("Ligue_1");

  // players list for navbar search (all leagues)
  const { players } = usePlayersList(null);

  const navigate = (target, name, league) => {
    if (target === "player" && name) {
      setPlayer(name);
      setPlayerLeague(league || "Ligue_1");
    }
    if (target === "explore" && league) {
      setExploreLeague(league);
    }
    setView(target);
  };

  return (
    <div className="min-h-screen bg-background text-text font-inter">
      <Navbar
        view={view}
        onNavigate={navigate}
        players={players}
        onSearch={(name, league) => navigate("player", name, league)}
        currentLeague={view === "player" ? playerLeague : view === "explore" ? exploreLeague : null}
      />

      {view === "home"    && <HomePage   onNavigate={navigate} />}
      {view === "player"  && <PlayerPage playerName={player} league={playerLeague} />}
      {view === "explore" && <ExplorePage onNavigate={navigate} league={exploreLeague} />}
    </div>
  );
}
