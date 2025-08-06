/**
 * Three.js Visualization for MedSafe
 * 3D visualization of medications and interaction graphs
 */

class ThreeVisualization {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.medicationMesh = null;
        this.interactionGraph = null;
        this.isShowingGraph = false;
        
        this.init();
    }

    init() {
        this.setupScene();
        this.setupCamera();
        this.setupRenderer();
        this.setupLights();
        this.setupControls();
        
        this.animate();
        this.handleResize();
    }

    setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf8fafc);
        
        // Add subtle fog
        this.scene.fog = new THREE.Fog(0xf8fafc, 10, 50);
    }

    setupCamera() {
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
        this.camera.position.set(0, 5, 10);
    }

    setupRenderer() {
        this.renderer = new THREE.WebGLRenderer({ 
            antialias: true,
            alpha: true 
        });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        this.container.appendChild(this.renderer.domElement);
    }

    setupLights() {
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        // Directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(10, 10, 5);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);

        // Point light for accent
        const pointLight = new THREE.PointLight(0x667eea, 0.5, 20);
        pointLight.position.set(-5, 5, 5);
        this.scene.add(pointLight);
    }

    setupControls() {
        // Simple orbital controls
        this.setupOrbitControls();
    }

    setupOrbitControls() {
        let isDragging = false;
        let previousMousePosition = { x: 0, y: 0 };

        this.container.addEventListener('mousedown', (e) => {
            isDragging = true;
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });

        this.container.addEventListener('mousemove', (e) => {
            if (!isDragging) return;

            const deltaMove = {
                x: e.clientX - previousMousePosition.x,
                y: e.clientY - previousMousePosition.y
            };

            const deltaRotationQuaternion = new THREE.Quaternion()
                .setFromEuler(new THREE.Euler(
                    toRadians(deltaMove.y * 1),
                    toRadians(deltaMove.x * 1),
                    0,
                    'XYZ'
                ));

            this.camera.quaternion.multiplyQuaternions(deltaRotationQuaternion, this.camera.quaternion);
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });

        this.container.addEventListener('mouseup', () => {
            isDragging = false;
        });

        // Zoom with mouse wheel
        this.container.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 1.1 : 0.9;
            this.camera.position.multiplyScalar(delta);
        });

        function toRadians(angle) {
            return angle * (Math.PI / 180);
        }
    }

    createMedicationMesh() {
        const group = new THREE.Group();

        // Pill capsule
        const capsuleGeometry = new THREE.CapsuleGeometry(0.8, 2, 4, 8);
        const capsuleMaterial = new THREE.MeshLambertMaterial({ 
            color: 0x667eea,
            transparent: true,
            opacity: 0.9
        });
        const capsule = new THREE.Mesh(capsuleGeometry, capsuleMaterial);
        capsule.castShadow = true;
        capsule.receiveShadow = true;
        group.add(capsule);

        // Pills around the main capsule
        for (let i = 0; i < 6; i++) {
            const pillGeometry = new THREE.SphereGeometry(0.3, 8, 6);
            const pillMaterial = new THREE.MeshLambertMaterial({ 
                color: new THREE.Color().setHSL((i * 60) / 360, 0.7, 0.6)
            });
            const pill = new THREE.Mesh(pillGeometry, pillMaterial);
            
            const angle = (i / 6) * Math.PI * 2;
            pill.position.x = Math.cos(angle) * 3;
            pill.position.z = Math.sin(angle) * 3;
            pill.position.y = Math.sin(angle) * 0.5;
            
            pill.castShadow = true;
            pill.receiveShadow = true;
            group.add(pill);
        }

        // Add floating particles
        this.addFloatingParticles(group);

        return group;
    }

    addFloatingParticles(group) {
        const particleGeometry = new THREE.SphereGeometry(0.05, 4, 4);
        const particleMaterial = new THREE.MeshBasicMaterial({ 
            color: 0xffffff,
            transparent: true,
            opacity: 0.6
        });

        for (let i = 0; i < 20; i++) {
            const particle = new THREE.Mesh(particleGeometry, particleMaterial);
            particle.position.set(
                (Math.random() - 0.5) * 10,
                (Math.random() - 0.5) * 8,
                (Math.random() - 0.5) * 10
            );
            
            // Add animation data
            particle.userData = {
                originalY: particle.position.y,
                speed: Math.random() * 0.02 + 0.01
            };
            
            group.add(particle);
        }
    }

    createInteractionGraph(analysisData) {
        const group = new THREE.Group();

        if (!analysisData || !analysisData.drug_interactions) {
            return group;
        }

        // Central medication node
        const centralGeometry = new THREE.SphereGeometry(1, 16, 12);
        const centralMaterial = new THREE.MeshLambertMaterial({ color: 0x667eea });
        const centralNode = new THREE.Mesh(centralGeometry, centralMaterial);
        centralNode.position.set(0, 0, 0);
        centralNode.castShadow = true;
        group.add(centralNode);

        // Add label to central node
        this.addTextLabel(group, analysisData.medication.name, centralNode.position, 0x667eea);

        // Interaction nodes
        const interactions = analysisData.drug_interactions;
        const nodeCount = Math.min(interactions.length, 8); // Limit to 8 interactions

        for (let i = 0; i < nodeCount; i++) {
            const interaction = interactions[i];
            const angle = (i / nodeCount) * Math.PI * 2;
            const radius = 4;
            
            // Position calculation
            const x = Math.cos(angle) * radius;
            const z = Math.sin(angle) * radius;
            const y = (Math.random() - 0.5) * 2;

            // Node color based on risk level
            const nodeColor = this.getRiskColor(interaction.risk_level);
            
            // Create interaction node
            const nodeGeometry = new THREE.SphereGeometry(0.6, 12, 8);
            const nodeMaterial = new THREE.MeshLambertMaterial({ color: nodeColor });
            const node = new THREE.Mesh(nodeGeometry, nodeMaterial);
            node.position.set(x, y, z);
            node.castShadow = true;
            group.add(node);

            // Connection line
            const lineGeometry = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(x, y, z)
            ]);
            const lineMaterial = new THREE.LineBasicMaterial({ 
                color: nodeColor,
                opacity: 0.7,
                transparent: true
            });
            const line = new THREE.Line(lineGeometry, lineMaterial);
            group.add(line);

            // Add text label
            this.addTextLabel(group, interaction.interacting_drug, node.position, nodeColor);

            // Add pulsing effect for high-risk interactions
            if (interaction.risk_level === 'alto' || interaction.risk_level === 'critico') {
                node.userData.pulse = true;
            }
        }

        // Add risk level indicators
        this.addRiskLevelIndicators(group, analysisData.overall_risk);

        return group;
    }

    getRiskColor(riskLevel) {
        switch(riskLevel) {
            case 'baixo': return 0x00b894;
            case 'medio': return 0xf39c12;
            case 'alto': return 0xff6348;
            case 'critico': return 0xff6b6b;
            default: return 0x74b9ff;
        }
    }

    addTextLabel(group, text, position, color) {
        // Create a simple text representation using planes
        // In a real implementation, you might want to use TextGeometry or canvas-based textures
        
        const labelGeometry = new THREE.PlaneGeometry(2, 0.5);
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        
        const context = canvas.getContext('2d');
        context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.fillStyle = 'white';
        context.font = 'bold 20px Arial';
        context.textAlign = 'center';
        context.fillText(text.substring(0, 15), canvas.width / 2, canvas.height / 2 + 7);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelMaterial = new THREE.MeshBasicMaterial({ 
            map: texture,
            transparent: true,
            opacity: 0.8
        });
        
        const label = new THREE.Mesh(labelGeometry, labelMaterial);
        label.position.copy(position);
        label.position.y += 1.5;
        label.lookAt(this.camera.position);
        
        group.add(label);
    }

    addRiskLevelIndicators(group, overallRisk) {
        const riskColor = this.getRiskColor(overallRisk);
        
        // Create risk level ring
        const ringGeometry = new THREE.TorusGeometry(6, 0.1, 8, 100);
        const ringMaterial = new THREE.MeshBasicMaterial({ 
            color: riskColor,
            transparent: true,
            opacity: 0.5
        });
        const ring = new THREE.Mesh(ringGeometry, ringMaterial);
        ring.rotation.x = Math.PI / 2;
        group.add(ring);

        // Add animated particles around the ring
        for (let i = 0; i < 12; i++) {
            const particleGeometry = new THREE.SphereGeometry(0.1, 6, 6);
            const particleMaterial = new THREE.MeshBasicMaterial({ color: riskColor });
            const particle = new THREE.Mesh(particleGeometry, particleMaterial);
            
            const angle = (i / 12) * Math.PI * 2;
            particle.position.x = Math.cos(angle) * 6;
            particle.position.z = Math.sin(angle) * 6;
            particle.position.y = 0;
            
            particle.userData = {
                angle: angle,
                speed: 0.02
            };
            
            group.add(particle);
        }
    }

    showMedication() {
        this.clearScene();
        
        this.medicationMesh = this.createMedicationMesh();
        this.scene.add(this.medicationMesh);
        
        this.isShowingGraph = false;
        
        // Reset camera position
        this.camera.position.set(0, 5, 10);
        this.camera.lookAt(0, 0, 0);
    }

    showInteractionGraph(analysisData) {
        this.clearScene();
        
        this.interactionGraph = this.createInteractionGraph(analysisData);
        this.scene.add(this.interactionGraph);
        
        this.isShowingGraph = true;
        
        // Adjust camera for graph view
        this.camera.position.set(0, 8, 12);
        this.camera.lookAt(0, 0, 0);
    }

    clearScene() {
        while(this.scene.children.length > 0) {
            const child = this.scene.children[0];
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
            }
            this.scene.remove(child);
        }
        
        // Re-add lights
        this.setupLights();
    }

    animate() {
        requestAnimationFrame(() => this.animate());

        // Animate medication mesh
        if (this.medicationMesh) {
            this.medicationMesh.rotation.y += 0.01;
            
            // Animate floating particles
            this.medicationMesh.children.forEach(child => {
                if (child.userData.speed) {
                    child.position.y = child.userData.originalY + Math.sin(Date.now() * child.userData.speed) * 0.5;
                }
            });
        }

        // Animate interaction graph
        if (this.interactionGraph) {
            this.interactionGraph.rotation.y += 0.005;
            
            // Animate pulsing nodes
            this.interactionGraph.children.forEach(child => {
                if (child.userData.pulse) {
                    const scale = 1 + Math.sin(Date.now() * 0.005) * 0.2;
                    child.scale.setScalar(scale);
                }
                
                // Animate ring particles
                if (child.userData.speed) {
                    child.userData.angle += child.userData.speed;
                    child.position.x = Math.cos(child.userData.angle) * 6;
                    child.position.z = Math.sin(child.userData.angle) * 6;
                }
            });
        }

        this.renderer.render(this.scene, this.camera);
    }

    handleResize() {
        window.addEventListener('resize', () => {
            const width = this.container.clientWidth;
            const height = this.container.clientHeight;

            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(width, height);
        });
    }

    dispose() {
        this.clearScene();
        this.renderer.dispose();
        if (this.container.contains(this.renderer.domElement)) {
            this.container.removeChild(this.renderer.domElement);
        }
    }
}