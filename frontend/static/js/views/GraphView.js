/**
 * GraphView - Interactive graph visualization with cosmic theme
 * Visualizes news as planets, stories as stars, in a space-like environment
 */
class GraphView {
    constructor(containerId, eventBus, apiBase) {
        this.container = document.getElementById(containerId);
        this.eventBus = eventBus;
        this.apiBase = apiBase || '/api';
        console.log('GraphView initialized with apiBase:', this.apiBase);

        this.stories = [];
        this.currentStoryId = null;
        this.graphData = null;
        this.graph = null;
        this.showActors = false;

        // Cosmic theme colors
        this.colors = {
            background: '#0a0e27',
            newsNode: '#4a90e2',
            storyNode: '#ffd700',
            actorNode: '#9b59b6',
            edge: '#3a6ea5',
            highlight: '#ff6b6b'
        };
    }

    /**
     * Render the graph visualization
     */
    async render() {
        console.log('GraphView.render called');
        this.container.innerHTML = `
            <div class="graph-controls">
                <button class="control-btn" id="resetGraphBtn" title="Reset View">
                    <i class="fas fa-compress-arrows-alt"></i> Reset
                </button>
                <button class="control-btn" id="toggleActorsBtn" title="Toggle Actors">
                    <i class="fas fa-users"></i> Toggle Actors
                </button>
            </div>
            <div id="graph-viz"></div>
            <div class="graph-loading">
                <div class="spinner"></div>
                <span>Loading cosmic map...</span>
            </div>
        `;

        try {
            // Fetch graph data from API
            console.log(`Fetching graph data from ${this.apiBase}/graph/news`);
            const response = await fetch(`${this.apiBase}/graph/news`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.graphData = await response.json();
            console.log('Graph data received:', this.graphData);

            if (!this.graphData || !this.graphData.nodes || this.graphData.nodes.length === 0) {
                console.warn('Graph data is empty or invalid');
                this.showError('No graph data available');
                return;
            }

            this.renderGraph();
        } catch (error) {
            console.error('Error loading graph:', error);
            this.showError('Failed to load graph data');
        }
    }

    /**
     * Render graph visualization
     */
    renderGraph() {
        console.log('Rendering graph...');
        this.initializeGraph();
    }

    /**
     * Initialize Force Graph visualization
     */
    initializeGraph() {
        try {
            console.log('Initializing graph...');
            // Clear container
            this.container.innerHTML = '';

            // Create graph container
            const graphContainer = document.createElement('div');
            graphContainer.id = 'graph-canvas';
            graphContainer.style.width = '100%';
            graphContainer.style.height = '100%';
            graphContainer.style.background = this.colors.background;
            this.container.appendChild(graphContainer);

            // Add Starfield Background
            const starfield = document.createElement('canvas');
            starfield.style.position = 'absolute';
            starfield.style.top = '0';
            starfield.style.left = '0';
            starfield.style.width = '100%';
            starfield.style.height = '100%';
            starfield.style.pointerEvents = 'none'; // Let clicks pass through
            starfield.style.zIndex = '0'; // Behind graph
            this.container.insertBefore(starfield, graphContainer);

            // Generate stars
            this.generateStarfield(starfield);

            // Create controls
            this.createControls();

            // Prepare graph data
            const graphData = this.prepareGraphData();

            // Initialize Force Graph
            this.graph = ForceGraph()(graphContainer)
                .graphData(graphData)
                .nodeId('id')
                .nodeLabel(node => this.getNodeLabel(node))
                .nodeColor(node => this.getNodeColor(node))
                .nodeVal(node => this.getNodeSize(node))
                .nodeCanvasObject((node, ctx, globalScale) => {
                    this.drawNode(node, ctx, globalScale);
                })
                .linkColor(() => this.colors.edge)
                .linkWidth(link => link.weight * 2)
                .linkOpacity(0.15) // Fainter links for cosmic look
                .linkDirectionalParticles(0)
                .onNodeClick(node => this.handleNodeClick(node))
                .onNodeHover(node => this.handleNodeHover(node))
                .cooldownTicks(100)
                .d3AlphaDecay(0.02)
                .d3VelocityDecay(0.3);

            // Apply story clustering forces
            this.applyStoryClusteringForces();
            console.log('Graph initialized successfully');
        } catch (error) {
            console.error('Error initializing graph:', error);
            this.showError(`Failed to initialize graph: ${error.message}`);
        }
    }

    /**
     * Prepare graph data with story clustering
     */
    prepareGraphData() {
        console.log('Preparing graph data:', this.graphData);
        if (!this.graphData) return { nodes: [], links: [] };

        const nodes = [];
        const links = [];

        // Add story nodes (stars)
        if (this.graphData.stories) {
            this.graphData.stories.forEach(story => {
                nodes.push({
                    id: `story_${story.id}`,
                    type: 'story',
                    storyId: story.id,
                    title: story.title,
                    size: story.size,
                    domain: story.domain
                });
            });
        } else {
            console.warn('No stories found in graph data');
        }

        // Add news nodes (planets)
        this.graphData.nodes.forEach(news => {
            nodes.push({
                id: news.id,
                type: 'news',
                title: news.title,
                storyId: news.story_id,
                domains: news.domains,
                isPinned: news.is_pinned
            });
        });

        // Add news-news similarity links
        this.graphData.links.forEach(link => {
            links.push({
                source: link.source,
                target: link.target,
                weight: link.weight,
                type: 'similarity'
            });
        });

        // Add virtual links to story centers
        this.graphData.nodes.forEach(news => {
            if (news.story_id) {
                links.push({
                    source: news.id,
                    target: `story_${news.story_id}`,
                    weight: 0.5,
                    type: 'story_membership'
                });
            }
        });

        return { nodes, links };
    }

    /**
     * Draw custom node with cosmic glow effect
     */
    /**
     * Draw custom node with cosmic glow effect
     */
    drawNode(node, ctx, globalScale) {
        if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

        const size = this.getNodeSize(node);
        if (!Number.isFinite(size) || size <= 0) return;

        const color = this.getNodeColor(node);

        if (node.type === 'story') {
            // --- STAR RENDERING ---

            // 1. Outer Glow (Corona)
            const glowRadius = size * 4;
            try {
                const gradient = ctx.createRadialGradient(node.x, node.y, size, node.x, node.y, glowRadius);
                gradient.addColorStop(0, color); // Core color
                gradient.addColorStop(0.2, color + '80'); // Semi-transparent
                gradient.addColorStop(1, 'transparent');

                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(node.x, node.y, glowRadius, 0, 2 * Math.PI);
                ctx.fill();
            } catch (e) {
                // Fallback if gradient fails
            }

            // 2. Core Star
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
            ctx.fillStyle = '#fff'; // Hot white center
            ctx.fill();

            // 3. Inner Tint
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
            ctx.fillStyle = color + '80'; // Tint over white
            ctx.fill();

            // Label for stars (always visible if large enough)
            if (globalScale > 0.2) {
                const fontSize = 14 / globalScale;
                ctx.font = `bold ${fontSize}px Sans-Serif`;
                ctx.fillStyle = '#ffffff';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.shadowColor = 'black';
                ctx.shadowBlur = 4;
                ctx.fillText(node.title, node.x, node.y + size + fontSize);
                ctx.shadowBlur = 0; // Reset
            }

        } else if (node.type === 'news') {
            // --- PLANET RENDERING ---

            // 1. Planet Body
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();

            // 2. Atmosphere/Shadow (Spherical effect)
            const gradient = ctx.createRadialGradient(
                node.x - size * 0.3,
                node.y - size * 0.3,
                size * 0.1,
                node.x,
                node.y,
                size
            );
            gradient.addColorStop(0, '#ffffff40'); // Highlight
            gradient.addColorStop(0.5, 'transparent');
            gradient.addColorStop(1, '#00000060'); // Shadow

            ctx.fillStyle = gradient;
            ctx.fill();

            // 3. Ring (optional, for pinned items)
            if (node.isPinned) {
                ctx.beginPath();
                ctx.ellipse(node.x, node.y, size * 1.8, size * 0.6, Math.PI / 4, 0, 2 * Math.PI);
                ctx.strokeStyle = '#ffffff80';
                ctx.lineWidth = 1 / globalScale;
                ctx.stroke();
            }

        } else if (node.type === 'actor') {
            // --- ACTOR RENDERING ---
            ctx.beginPath();
            const side = size * 1.5;
            ctx.rect(node.x - side / 2, node.y - side / 2, side, side);
            ctx.fillStyle = color;
            ctx.fill();

            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1 / globalScale;
            ctx.stroke();

            if (globalScale > 1.5) {
                const fontSize = 8 / globalScale;
                ctx.font = `${fontSize}px Sans-Serif`;
                ctx.fillStyle = '#ffffff';
                ctx.textAlign = 'center';
                ctx.fillText(node.name, node.x, node.y + side);
            }
        }
    }

    /**
     * Get node color based on type and domain
     */
    getNodeColor(node) {
        if (node.type === 'story') {
            return this.colors.storyNode;
        } else if (node.type === 'actor') {
            return this.colors.actorNode;
        } else {
            // Color by domain
            const domainColors = {
                'politics': '#e74c3c',
                'economics': '#2ecc71',
                'technology': '#4a90e2',
                'culture': '#9b59b6',
                'military': '#e67e22'
            };
            return domainColors[node.domains?.[0]] || this.colors.newsNode;
        }
    }

    /**
     * Get node size
     */
    getNodeSize(node) {
        if (node.type === 'story') {
            return 8 + node.size * 0.5;
        } else if (node.type === 'actor') {
            return 5;
        } else {
            return node.isPinned ? 6 : 4;
        }
    }

    /**
     * Get node label for tooltip
     */
    getNodeLabel(node) {
        if (node.type === 'story') {
            return `📊 ${node.title} (${node.size} news)`;
        } else if (node.type === 'actor') {
            return `👤 ${node.name}`;
        } else {
            return `📰 ${node.title}`;
        }
    }

    /**
     * Apply custom forces for story clustering
     */
    applyStoryClusteringForces() {
        if (!this.graph) return;

        // 1. Radial Force: Keep planets orbiting their story stars
        this.graph.d3Force('orbit', d3.forceRadial(d => {
            if (d.type === 'news' && d.storyId) {
                return 60; // Orbit radius
            }
            return 0;
        }, d => {
            // Center of the orbit is the story node
            // Note: This is tricky in d3-force as radial force usually has a static center.
            // We rely on links to pull them close, and collision to keep them apart.
            // Instead, we'll use a custom force to group stories by domain.
            return 0;
        }).strength(0)); // Disable standard radial for now, rely on links

        // 2. Domain Clustering: Pull stories of same domain together
        // We can't easily add a custom d3 force here without more complex logic,
        // so we'll rely on a ManyBody force with positive strength for same-domain stories?
        // No, standard approach: invisible links between stories of same domain.

        // Alternative: Use d3-force-cluster if available, or just rely on link forces.
        // Let's just increase link strength for story-news and add collision.

        this.graph.d3Force('charge').strength(node => {
            if (node.type === 'story') return -300; // Strong repulsion for stars
            return -30; // Weaker repulsion for planets
        });

        this.graph.d3Force('collide', d3.forceCollide(node => {
            return this.getNodeSize(node) + 4; // Prevent overlap
        }));
    }

    /**
     * Handle node click
     */
    handleNodeClick(node) {
        if (!node) return;

        if (node.type === 'story') {
            this.selectStory(node.storyId);
        } else if (node.type === 'news') {
            this.eventBus.emit('news:selected', node.id);
        } else if (node.type === 'actor') {
            this.eventBus.emit('actor:selected', node.id);
        }
    }

    /**
     * Handle node hover
     */
    handleNodeHover(node) {
        if (!this.graph) return;

        // Highlight connected nodes
        if (node) {
            const linkedNodeIds = new Set();
            this.graph.graphData().links
                .filter(link => link.source.id === node.id || link.target.id === node.id)
                .forEach(link => {
                    linkedNodeIds.add(link.source.id);
                    linkedNodeIds.add(link.target.id);
                });

            // Update node colors
            this.graph.nodeColor(n => {
                return linkedNodeIds.has(n.id) ? this.colors.highlight : this.getNodeColor(n);
            });
        } else {
            // Reset colors
            this.graph.nodeColor(n => this.getNodeColor(n));
        }
    }

    /**
     * Select a story
     * @param {string} storyId - Story ID
     */
    selectStory(storyId) {
        this.currentStoryId = storyId;
        this.eventBus.emit('story:selected', storyId);

        // Highlight story and its news
        if (this.graph) {
            this.graph.nodeColor(node => {
                if (node.storyId === storyId || node.id === `story_${storyId}`) {
                    return this.colors.highlight;
                }
                return this.getNodeColor(node);
            });
        }
    }

    /**
     * Create legend
     */
    createLegend() {
        const legend = document.createElement('div');
        legend.className = 'graph-legend';
        legend.innerHTML = `
            <div class="legend-title">Cosmic Map</div>
            <div class="legend-item">
                <div class="legend-color star"></div>
                <span>Story (Star)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color planet"></div>
                <span>News (Planet)</span>
            </div>
            <div class="legend-item" id="legendActor" style="display: none;">
                <div class="legend-color actor"></div>
                <span>Actor</span>
            </div>
        `;
        this.container.appendChild(legend);
        this.legend = legend;
    }

    /**
     * Create control buttons
     */
    createControls() {
        const controls = document.createElement('div');
        controls.className = 'graph-controls';
        controls.innerHTML = `
            <button id="toggleActors" class="graph-btn">Toggle Actors</button>
            <button id="zoomReset" class="graph-btn">Reset View</button>
        `;
        this.container.appendChild(controls);

        // Create Legend
        this.createLegend();

        // Add event listeners
        document.getElementById('toggleActors')?.addEventListener('click', () => {
            this.toggleActorLayer();
        });

        document.getElementById('zoomReset')?.addEventListener('click', () => {
            if (this.graph) {
                this.graph.zoomToFit(400);
            }
        });
    }

    /**
     * Toggle actor layer visibility
     */
    async toggleActorLayer() {
        this.showActors = !this.showActors;

        if (this.showActors && !this.actorData) {
            // Fetch actor data
            try {
                const response = await fetch(`${this.apiBase}/graph/actors`);
                this.actorData = await response.json();
                this.addActorLayer();
            } catch (error) {
                console.error('Failed to load actors:', error);
            }
        } else if (this.showActors) {
            this.addActorLayer();
        } else {
            this.removeActorLayer();
        }

        // Toggle legend item
        const legendActor = this.legend?.querySelector('#legendActor');
        if (legendActor) {
            legendActor.style.display = this.showActors ? 'flex' : 'none';
        }
    }

    /**
     * Add actor layer to graph
     */
    addActorLayer() {
        if (!this.graph || !this.actorData) return;

        const currentData = this.graph.graphData();

        // Add actor nodes
        this.actorData.nodes.forEach(actor => {
            currentData.nodes.push({
                id: actor.id,
                type: 'actor',
                name: actor.name,
                actorType: actor.actor_type
            });
        });

        // Add actor-news mentions
        this.actorData.mentions.forEach(mention => {
            currentData.links.push({
                source: mention.news_id,
                target: mention.actor_id,
                type: 'mention',
                weight: 0.3
            });
        });

        this.graph.graphData(currentData);
    }

    /**
     * Remove actor layer from graph
     */
    removeActorLayer() {
        if (!this.graph) return;

        const currentData = this.graph.graphData();

        // Remove actor nodes and links
        currentData.nodes = currentData.nodes.filter(n => n.type !== 'actor');
        currentData.links = currentData.links.filter(l => l.type !== 'mention');

        this.graph.graphData(currentData);
    }

    /**
     * Show placeholder message
     */
    showPlaceholder(message) {
        this.container.innerHTML = `
            <div class="graph-placeholder" style="padding: 40px; text-align: center; color: #8b9dc3;">
                <h3>Graph View</h3>
                <p>${message}</p>
            </div>
        `;
    }

    /**
     * Clear the graph
     */
    clear() {
        this.container.innerHTML = '';
        this.stories = [];
        this.currentStoryId = null;
        this.graph = null;
    }

    /**
     * Show loading state
     */
    showLoading() {
        this.container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading graph...</div>';
    }
    /**
     * Generate static starfield background
     */
    generateStarfield(canvas) {
        const ctx = canvas.getContext('2d');
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;

        canvas.width = width;
        canvas.height = height;

        // Clear
        ctx.clearRect(0, 0, width, height);

        // Draw random stars
        const starCount = 200;
        ctx.fillStyle = '#ffffff';

        for (let i = 0; i < starCount; i++) {
            const x = Math.random() * width;
            const y = Math.random() * height;
            const size = Math.random() * 1.5;
            const opacity = Math.random();

            ctx.globalAlpha = opacity;
            ctx.beginPath();
            ctx.arc(x, y, size, 0, 2 * Math.PI);
            ctx.fill();
        }
        ctx.globalAlpha = 1.0;
    }
}
