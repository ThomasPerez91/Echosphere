import type { useColony } from '../hooks/useColony';
import { ColonyScreen } from './ColonyScreen';
import { Badge, EmptyState } from './ui';

const colonyViews = [
  { id: 'overview', label: 'Vue d’ensemble', title: 'Aucune colonie active', description: 'Le bilan de votre colonie et ses prochaines échéances apparaîtront ici une fois une partie disponible.' },
  { id: 'infrastructure', label: 'Infrastructures', title: 'Vos secteurs, vos choix', description: 'Les infrastructures, leurs niveaux et la file de construction seront accessibles depuis cet espace. Aucun bâtiment ou stock de démonstration n’est affiché.' },
  { id: 'orbit', label: 'Orbite', title: 'L’orbite reste à explorer', description: 'Les emplacements orbitaux et leurs infrastructures feront l’objet d’une prochaine étape.' },
  { id: 'defense', label: 'Défense', title: 'Défense — système futur', description: 'La défense planétaire sera gérée dans la colonie. Les modules, réparations et effets de combat ne sont pas encore disponibles.' },
] as const;

export function ColonyView({ view, universe = false, link = (value: string) => `#${value}`, onNavigate, colony }: {
  view: string; universe?: boolean; link?: (value: string) => string; onNavigate?: () => void; colony?: ReturnType<typeof useColony>;
}) {
  if (universe && colony) return <ColonyScreen colony={colony} view={view} link={link} onNavigate={onNavigate} />;
  const selected = colonyViews.find(item => item.id === view);
  return <section className="colony-view" aria-label="Gestion de la colonie">
    <nav aria-label="Sections de la colonie" className="colony-navigation">
      {colonyViews.map(item => <a key={item.id} href={link(`colony/${item.id}`)} onClick={onNavigate}
        aria-current={item.id === view ? 'page' : undefined}>{item.label}</a>)}
    </nav>
    <div className="panel destination-panel">
      <div className="colony-context"><Badge>{universe ? 'Aucune donnée de colonie disponible' : 'Aucun univers / aucune colonie active'}</Badge>
        <p>Les informations de votre colonie apparaîtront lorsqu’une partie pourra être ouverte.</p></div>
      <EmptyState title={selected?.title ?? 'Section introuvable'}>
        {selected?.description ?? 'Sélectionnez une section de la colonie ci-dessus.'}
      </EmptyState>
      <a className="text-link" href={link('empire')} onClick={onNavigate}>← Retour à l’Empire</a>
    </div>
  </section>;
}
