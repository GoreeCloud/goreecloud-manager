import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const root = path.resolve(import.meta.dirname, '..');
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8');
const json = relative => JSON.parse(read(relative));
const clone = value => JSON.parse(JSON.stringify(value));

const expected = Object.freeze({
  repository: 'GoreeCloud/goreecloud-manager',
  implementedVersion: '1.3.0',
  currentStableVersion: '1.5.0',
  currentStableQualificationAnchor: 'ee1032a0822ab8e103f8afe48e5c1859fde65cc9',
  historicalDevelopmentVersion: '1.5.0-dev.1',
  historicalDevelopmentRevision: 'e7c397837908e4644d6230f17d0f73e84e3d1558',
  historicalDevelopmentStableBaseline: '1.4.1',
  sharedProfileId: 'goreecloud-manager-desktop'
});

const contract = json('contracts/glaze-ui/manager-glaze-v1.5-development.json');
const platform = read('goreecloud.platform.yaml');
const glazeDoc = read('docs/glaze-ui.md');
const compatibilityDoc = read('docs/glaze-v1.5-development-compatibility.md');
const baseTemplate = read('core/templates/core/base.html');
const glazeCss = read('core/static/core/css/glaze-ui.css');
const glazeRoot = String(process.env.GLAZE_V15_ROOT || '').trim();

assert.ok(glazeRoot, 'GLAZE_V15_ROOT must point to the exact historical Glaze UI V1.5 Development checkout');
assert.ok(fs.existsSync(glazeRoot), `GLAZE_V15_ROOT does not exist: ${glazeRoot}`);
const upstreamRevision = execFileSync('git', ['-C', glazeRoot, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
assert.equal(upstreamRevision, expected.historicalDevelopmentRevision, 'historical Glaze V1.5 checkout must match the exact governed Development revision');

assert.equal(contract.schemaVersion, 1);
assert.equal(contract.documentVersion, '1.1');
assert.equal(contract.recordType, 'goreecloud-manager-glaze-v1.5-development-integration');
assert.equal(contract.consumer?.repository, expected.repository);
assert.equal(contract.consumer?.lifecycle, 'development');
assert.equal(contract.glazeUi?.implementedSourceTarget, expected.implementedVersion);
assert.equal(contract.glazeUi?.requiredStableTarget, expected.currentStableVersion);
assert.equal(contract.glazeUi?.requiredStableQualificationAnchor, expected.currentStableQualificationAnchor);
assert.equal(contract.glazeUi?.historicalDevelopmentVersion, expected.historicalDevelopmentVersion);
assert.equal(contract.glazeUi?.historicalDevelopmentRevision, expected.historicalDevelopmentRevision);
assert.equal(contract.glazeUi?.historicalDevelopmentStableBaseline, expected.historicalDevelopmentStableBaseline);
assert.equal(contract.glazeUi?.sharedRepresentativeProfile, expected.sharedProfileId);
assert.equal(contract.integrationBoundary?.developmentOnly, true);
assert.equal(contract.integrationBoundary?.testOnly, true);
assert.equal(contract.integrationBoundary?.runtimeDependencyAdded, false);
assert.equal(contract.integrationBoundary?.implementedV13SourceMappingPreserved, true);
assert.equal(contract.integrationBoundary?.requiredStable150TargetRecorded, true);
assert.equal(contract.integrationBoundary?.stable150MigrationCompleted, false);
assert.equal(contract.integrationBoundary?.historicalDevelopmentExerciseDoesNotEstablishStableMigration, true);
assert.equal(contract.integrationBoundary?.consumerAcceptanceEstablished, false);
assert.equal(contract.integrationBoundary?.releaseCandidateQualified, false);
assert.equal(contract.integrationBoundary?.stableQualified, false);
assert.equal(contract.integrationBoundary?.productionEligible, false);
assert.equal(contract.authorityBoundary?.glazeAuthority, 'presentation-only');
assert.equal(contract.authorityBoundary?.authorizationMayBeInferredByGlaze, false);
assert.equal(contract.authorityBoundary?.providerPrecedenceMayBeInferredByGlaze, false);
assert.equal(contract.authorityBoundary?.permissionMayBeGrantedByGlaze, false);
assert.equal(contract.authorityBoundary?.automaticNavigationAllowed, false);
assert.equal(contract.authorityBoundary?.consequentialExecutionMayBeAutomatic, false);
assert.equal(contract.authorityBoundary?.fallbackExecutionMayBeAutomatic, false);
assert.equal(contract.acceptance?.repositoryLocalConsumerAcceptance, false);
assert.equal(contract.acceptance?.productionAcceptance, false);
assert.equal(contract.validation?.scenarios?.length, 4);

// Preserve Manager's actual current source/migration truth. The historical
// Development exercise may not become a shipped runtime or an acceptance claim.
assert.ok(baseTemplate.includes('data-glaze-version="1.3.0"'));
assert.ok(glazeCss.includes('--glaze-contract-version: "1.3.0"'));
assert.ok(glazeDoc.includes("implemented source mapping remains Glaze UI V1.3 / `1.3.0`"));
assert.ok(glazeDoc.includes('required current Official Stable consumer target is **GLAZE UI V1.5 / `1.5.0`**'));
assert.ok(compatibilityDoc.includes('Historical Development Stable baseline:** `1.4.1`'));
assert.ok(compatibilityDoc.includes('Manager required current Stable Glaze target:** V1.5 / `1.5.0`'));
assert.match(platform, /lifecycle:\s*development/);
assert.match(platform, /result:\s*applicable-migration-required/);
assert.match(platform, /glaze_ui:\n\s+result:\s+applicable-migration-required\n\s+version:\s+1\.3\.0/);
assert.ok(platform.includes('glaze_ui_required: "1.5.0"'));
assert.ok(platform.includes('glaze-ui==1.5.0'));
assert.ok(platform.includes('conformance:\n  status: nonconformant'));
assert.ok(!platform.includes('glaze-ui==1.5.0-dev.1'));
assert.ok(!platform.includes('glaze_ui_required: "1.5.0-dev.1"'));

const upstreamRegistry = JSON.parse(fs.readFileSync(path.join(glazeRoot, 'registry/development/glaze-v1.5.0-dev.1.json'), 'utf8'));
const profiles = JSON.parse(fs.readFileSync(path.join(glazeRoot, 'contracts/v1.5/representative-consumers.dev.json'), 'utf8'));
assert.equal(upstreamRegistry.version, expected.historicalDevelopmentVersion);
assert.equal(upstreamRegistry.lifecycle, 'development');
assert.equal(upstreamRegistry.consumerEligible, false);
assert.equal(upstreamRegistry.stableBaseline, expected.historicalDevelopmentStableBaseline);
assert.equal(upstreamRegistry.representativeConsumerAcceptanceEstablished, false);
assert.equal(upstreamRegistry.representativeConsumerIntegrationChangesStableTarget, false);
assert.equal(profiles.version, expected.historicalDevelopmentVersion);
assert.equal(profiles.stableConsumerTarget, expected.historicalDevelopmentStableBaseline);
assert.equal(profiles.developmentOnly, true);
assert.equal(profiles.consumerAcceptanceEstablished, false);
assert.equal(profiles.repositoryLocalAcceptanceRequired, true);

const {resolveGlazeInterface} = await import(pathToFileURL(path.join(glazeRoot, 'js/glaze-v1.5-resolution.dev.mjs')).href);
const {glazeProviderDevelopmentContract} = await import(pathToFileURL(path.join(glazeRoot, 'js/glaze-v1.5-provider-registry.dev.mjs')).href);
assert.equal(glazeProviderDevelopmentContract.providerPrecedenceInferred, false);
assert.equal(glazeProviderDevelopmentContract.authorizationInferred, false);

const managerProfile = profiles.profiles.find(profile => profile.id === expected.sharedProfileId);
assert.ok(managerProfile, `Missing upstream representative Manager profile: ${expected.sharedProfileId}`);
assert.equal(managerProfile.repository, expected.repository);

function assertGlobalBoundaries(result) {
  assert.equal(result.version, expected.historicalDevelopmentVersion);
  assert.equal(result.lifecycle, 'development');
  assert.equal(result.stableBaseline, expected.historicalDevelopmentStableBaseline);
  assert.equal(result.authority.glazeAuthority, 'presentation-only');
  assert.equal(result.authority.authorizationInferred, false);
  assert.equal(result.authority.permissionGranted, false);
  assert.equal(result.authority.providerPrecedenceInferred, false);
  assert.equal(result.authority.operationalAuthorityGranted, false);
  assert.equal(result.authority.automaticNavigationAllowed, false);
  assert.equal(result.authority.automaticPermissionRequestAllowed, false);
  assert.equal(result.authority.automaticConsequentialExecutionAllowed, false);
  assert.equal(result.authority.automaticFallbackExecutionAllowed, false);
  assert.equal(result.continuity.taskStateReset, false);
  assert.equal(result.continuity.pageReloadRequired, false);
  assert.equal(result.privacy.localFirst, true);
  assert.equal(result.privacy.telemetryRequired, false);
  assert.equal(result.privacy.remoteAnalysisRequired, false);
  assert.equal(result.diagnostics.authority.operationalAuthorityGranted, false);
  assert.equal(result.diagnostics.authority.securityStateManufactured, false);
  assert.equal(result.diagnostics.authority.privacyStateManufactured, false);
  assert.equal(result.diagnostics.privacy.rawContextIncluded, false);
  assert.equal(result.diagnostics.privacy.providerIdentityIncluded, false);
}

const canonical = resolveGlazeInterface(clone(managerProfile.input));
assertGlobalBoundaries(canonical);
const canonicalRefresh = canonical.actions.actions.find(action => action.id === 'refresh-status');
const canonicalAdmin = canonical.actions.actions.find(action => action.id === 'apply-administrative-change');
const canonicalAdminDestination = canonical.navigation.destinations.find(item => item.id === 'administration');
assert.equal(canonicalRefresh.enabled, true);
assert.equal(canonicalAdmin.enabled, false);
assert.equal(canonicalAdmin.state, 'restricted');
assert.equal(canonicalAdmin.consequential, true);
assert.equal(canonicalAdmin.automaticExecutionAllowed, false);
assert.ok(canonicalAdmin.reasonCodes.includes('restricted-by-authority'));
assert.equal(canonicalAdminDestination.visible, true);
assert.equal(canonicalAdminDestination.enabled, false);
assert.equal(canonical.capabilities.byId['application.refresh'].provenance.authority, 'application');
assert.equal(canonical.capabilities.byId['authorization.manager-admin'].provenance.authority, 'policy');
assert.equal(JSON.stringify(canonical.diagnostics).includes('manager-policy'), false);
assert.equal(JSON.stringify(canonical.diagnostics).includes('goreecloud-manager-runtime'), false);

const authorizedInput = clone(managerProfile.input);
authorizedInput.providers.find(provider => provider.id === 'manager-policy').capabilities[0].state = 'available';
const authorized = resolveGlazeInterface(authorizedInput);
assertGlobalBoundaries(authorized);
const authorizedAdmin = authorized.actions.actions.find(action => action.id === 'apply-administrative-change');
const authorizedDestination = authorized.navigation.destinations.find(item => item.id === 'administration');
assert.equal(authorized.capabilities.byId['authorization.manager-admin'].state, 'available');
assert.equal(authorized.capabilities.byId['authorization.manager-admin'].provenance.authority, 'policy');
assert.equal(authorizedAdmin.enabled, true);
assert.equal(authorizedAdmin.consequential, true);
assert.equal(authorizedAdmin.automaticExecutionAllowed, false);
assert.equal(authorizedDestination.visible, true);
assert.equal(authorizedDestination.enabled, true);
assert.equal(authorized.authority.automaticNavigationAllowed, false);

const conflictInput = clone(managerProfile.input);
conflictInput.providers.push({
  id: 'duplicate-manager-policy',
  authority: 'policy',
  capabilities: [{id: 'authorization.manager-admin', domain: 'authorization', state: 'available'}]
});
const conflict = resolveGlazeInterface(conflictInput);
assertGlobalBoundaries(conflict);
assert.ok(conflict.conflicts.capabilityIds.includes('authorization.manager-admin'));
assert.equal(conflict.capabilities.byId['authorization.manager-admin'], undefined);
const conflictRefresh = conflict.actions.actions.find(action => action.id === 'refresh-status');
const conflictAdmin = conflict.actions.actions.find(action => action.id === 'apply-administrative-change');
assert.equal(conflictRefresh.enabled, true);
assert.equal(conflictAdmin.enabled, false);
assert.equal(conflictAdmin.state, 'unknown');
assert.ok(conflictAdmin.reasonCodes.includes('capability-unknown'));
assert.equal(conflict.authority.providerPrecedenceInferred, false);

const unavailableInput = clone(managerProfile.input);
unavailableInput.providers.find(provider => provider.id === 'goreecloud-manager-runtime').capabilities[0].state = 'temporarily-unavailable';
const unavailable = resolveGlazeInterface(unavailableInput);
assertGlobalBoundaries(unavailable);
const unavailableRefresh = unavailable.actions.actions.find(action => action.id === 'refresh-status');
const unavailableAdmin = unavailable.actions.actions.find(action => action.id === 'apply-administrative-change');
assert.equal(unavailableRefresh.enabled, false);
assert.equal(unavailableRefresh.state, 'temporarily-unavailable');
assert.ok(unavailableRefresh.reasonCodes.includes('temporarily-unavailable'));
assert.equal(unavailableAdmin.enabled, false);
assert.equal(unavailableAdmin.state, 'restricted');
assert.equal(unavailable.capabilities.byId['authorization.manager-admin'].provenance.authority, 'policy');
assert.equal(unavailable.authority.authorizationInferred, false);

console.log('GoreeCloud Manager / historical GLAZE UI 1.5.0-dev.1 compatibility: PASS');
console.log(`Historical exact upstream Glaze revision: ${expected.historicalDevelopmentRevision}`);
console.log(`Historical Development Stable baseline: ${expected.historicalDevelopmentStableBaseline}`);
console.log(`Manager implemented Glaze source remains: ${expected.implementedVersion}`);
console.log(`Manager required current Stable Glaze target: ${expected.currentStableVersion}`);
console.log('Manager current Stable V1.5 migration / consumer acceptance / production acceptance established: false');
