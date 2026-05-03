// ============================================================
// India Regional Development Analytics System
// Neo4j Cypher Query Reference
// ============================================================
// Run these in the Neo4j Browser at http://localhost:7474
// or via the neo4j Python driver
// ============================================================


// ── 1. Full hierarchy: Country → State → District ────────────

MATCH path = (c:Country {name: 'India'})<-[:BELONGS_TO*1..2]-(leaf)
RETURN path LIMIT 50


// ── 2. All districts in a state ──────────────────────────────

MATCH (d:District)-[:BELONGS_TO]->(s:State {name: 'Karnataka'})
RETURN d.name AS district, d.dev_score AS score, d.cluster AS cluster
ORDER BY d.dev_score DESC


// ── 3. Aspirational districts (lowest development cluster) ───

MATCH (d:District)
WHERE d.cluster = 'Aspirational'
RETURN d.name AS district, d.dev_score AS score, d.dev_rank AS rank
ORDER BY d.dev_score ASC
LIMIT 30


// ── 4. Find districts bordering a given district ─────────────

MATCH (d:District {name: 'Pune'})-[:BORDERS]-(neighbor:District)
RETURN neighbor.name AS neighbor, neighbor.dev_score AS dev_score,
       neighbor.cluster AS cluster
ORDER BY neighbor.dev_score DESC


// ── 5. Districts similar in development level ────────────────

MATCH (d:District {name: 'Wayanad'})-[r:SIMILAR_DEVELOPMENT_LEVEL]-(similar:District)
RETURN similar.name AS district, similar.dev_score AS score,
       r.score_diff AS score_diff
ORDER BY r.score_diff ASC
LIMIT 15


// ── 6. Shortest path between two districts (via borders) ─────

MATCH (a:District {name: 'Leh'}), (b:District {name: 'Kanyakumari'}),
      path = shortestPath((a)-[:BORDERS*]-(b))
RETURN [n IN nodes(path) | n.name] AS route, length(path) AS hops


// ── 7. State-level development summary ───────────────────────

MATCH (d:District)-[:BELONGS_TO]->(s:State)
WHERE d.dev_score > 0
WITH s, 
     avg(d.dev_score)   AS avg_score,
     min(d.dev_score)   AS min_score,
     max(d.dev_score)   AS max_score,
     stdev(d.dev_score) AS stddev_score,
     count(d)           AS district_count
RETURN s.name AS state, 
       round(avg_score, 2) AS avg_dev_score,
       round(min_score, 2) AS min_score,
       round(max_score, 2) AS max_score,
       round(stddev_score, 3) AS within_state_inequality,
       district_count
ORDER BY avg_score DESC


// ── 8. Identify "development islands" ────────────────────────
// Districts significantly more developed than all their neighbors

MATCH (d:District)-[:BORDERS]->(neighbor:District)
WHERE d.dev_score > 0 AND neighbor.dev_score > 0
WITH d, collect(neighbor.dev_score) AS neighbor_scores
WHERE d.dev_score > reduce(maxScore = 0.0, s IN neighbor_scores | CASE WHEN s > maxScore THEN s ELSE maxScore END) + 10
RETURN d.name AS island_district, d.dev_score AS score,
       [s IN neighbor_scores | round(s, 1)] AS neighbor_scores
ORDER BY d.dev_score DESC


// ── 9. Cluster distribution per state ────────────────────────

MATCH (d:District)-[:BELONGS_TO]->(s:State)
RETURN s.name AS state, d.cluster AS cluster, count(d) AS count
ORDER BY s.name, count DESC


// ── 10. Cities by population in a district ───────────────────

MATCH (c:City)-[:LOCATED_IN]->(d:District)-[:BELONGS_TO]->(s:State)
WHERE d.name = 'Pune'
RETURN c.name AS city, c.population AS population, c.city_class AS class
ORDER BY c.population DESC


// ── 11. Regional inequality — NE vs South comparison ─────────

MATCH (d:District)-[:BELONGS_TO]->(s:State)
WHERE s.region IN ['NE', 'South']
WITH s.region AS region, collect(d.dev_score) AS scores
RETURN region,
       size(scores) AS districts,
       round(reduce(sum=0.0, s IN [x IN scores WHERE x > 0 | x] | sum) /
             size([x IN scores WHERE x > 0 | x]), 2) AS avg_score
ORDER BY avg_score DESC


// ── 12. Graph stats ──────────────────────────────────────────

MATCH (n)
WITH labels(n)[0] AS label, count(n) AS count
RETURN label, count
ORDER BY count DESC

MATCH ()-[r]->()
WITH type(r) AS rel_type, count(r) AS count
RETURN rel_type, count
ORDER BY count DESC
