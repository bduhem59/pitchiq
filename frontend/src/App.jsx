import { useState } from "react";
import Navbar       from "./components/Navbar";
import HomePage     from "./pages/HomePage";
import PlayerPage   from "./pages/PlayerPage";
import ExplorePage  from "./pages/ExplorePage";
import ComparePage  from "./pages/ComparePage";
import { usePlayersList } from "./hooks/usePlayersList";

export default function App() {
  const [view,          setView]          = useState("home");
  const [player,        setPlayer]        = useState(null);
  const [playerLeague,  setPlayerLeague]  = useState("Ligue_1");
  const [exploreLeague, setExploreLeague] = useState("Ligue_1");
  const [compareP1,     setCompareP1]     = useState(null);
  const [compareP1L,    setCompareP1L]    = useState("Ligue_1");
  const [compareP2,     setCompareP2]     = useState(null);
  const [compareP2L,    setCompareP2L]    = useState("Ligue_1");

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
      {view === "player"  && <PlayerPage playerName={player} league={playerLeague}
                                         players={players}
                                         onNavigate={navigate}
                                         onCompare={(p1, l1, p2, l2) => {
                                           setCompareP1(p1); setCompareP1L(l1);
                                           setCompareP2(p2); setCompareP2L(l2);
                                           setView("compare");
                                         }} />}
      {view === "explore" && <ExplorePage onNavigate={navigate} league={exploreLeague} />}
      {view === "compare" && compareP1 && compareP2 && (
        <ComparePage
          p1={compareP1}   p1League={compareP1L}
          p2={compareP2}   p2League={compareP2L}
          onBack={() => {
            setPlayer(compareP1); setPlayerLeague(compareP1L);
            setView("player");
          }}
          onNavigate={navigate}
        />
      )}
    </div>
  );
}
