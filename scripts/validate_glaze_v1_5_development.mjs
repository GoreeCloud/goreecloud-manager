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
  stableVersion: '1.4.1',
  stableRevision: '4fab9da0fad2e5c974e0e66ec88632c61745751c',
  developmentVersion: '1.5.0-dev.1',
  developmentRevision: 'e7c397837908e4644d6230f17d0f73e84e3d1558',
  sharedProfileId: 'goreecloud-manager-desktop'
});

const contract = json('contracts/glaze-ui/manager-glaze-v1.5-development.json');
const platform = read('goreecloud.platform.yaml');
const glazeDoc = read('docs/glaze-ui.md');
const baseTemplate = read('core/templates/core/base.html');
const glazeCss = read('core/static/core/css/glaze-ui.css');
const glazeRoot = String(process.env.GLAZE_V15_ROOT || '').trim();

assert.ok(glazeRoot, 'GLAZE_V15_ROOT must point to the exact Glaze UI V1.5 Development checkout');
assert.ok(fs.existsSync(glazeRoot), `GLAZE_V15_ROOT does not exist: ${glazeRoot}`);
const upstreamRevision = execFileSync('git', ['-C', glazeRoot, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
assert.equal(upstreamRevision, expected.developmentRevision, 'Glaze V1.5 checkout must match the exact governed Development revision');

assert.equal(contract.schemaVersion, 1);
assert.equal(contract.documentVersion, '1.0');
assert.equal(contract.recordType, 'goreecloud-manager-glaze-v1.5-development-integration');
assert.equal(contract.consumer?.repository, expected.repository);
assert.equal(contract.consumer?.lifecycle, 'development');
assert.equal(contract.glazeUi?.implementedSourceTarget, expected.implementedVersion);
assert.equal(contract.glazeUi?.requiredStableTarget, expected.stableVersion);
assert.equal(contract.glazeUi?.requiredStableRevision, expected.stableRevision);
assert.equal(contract.glazeUi?.developmentVersion, expected.developmentVersion);
assert.equal(contract.glazeUi?.developmentRevision, expected.developmentRevision);
assert.equal(contract.glazeUi?.sharedRepresentativeProfile, expected.sharedProfileId);
assert.equal(contract.integrationBoundary?.developmentOnly, true);
assert.equal(contract.integrationBoundary?.testOnly, true);
assert.equal(contract.integrationBoundary?.runtimeDependencyAdded, false);
assert.equal(contract.integrationBoundary?.platformManifestChangedByThisIntegration, false);
assert.equal(contract.integrationBoundary?.requiredStable141TargetPreserved, true);
assert.equal(contract.integrationBoundary?.implementedV13SourceMappingPreserved, true);
assert.equal(contract.integrationBoundary?.stable141MigrationCompleted, false);
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

// Preserve Manager's actual current source/migration truth and fail closed if V1.5 leaks into shipped declarations.
assert.ok(baseTemplate.includes('data-glaze-version="1.3.0"'));
assert.ok(glazeCss.includes('--glaze-contract-version: "1.3.0"'));
assert.ok(glazeDoc.includes("implemented source mapping remains Glaze UI V1.3 / `1.3.0`"));
assert.ok(glazeDoc.includes('required current Official Stable consumer target is **GLAZE UI V1.4.1 / `1.4.1`**'));
assert.match(platform, /lifecycle:\s*development/);
assert.match(platform, /result:\s*applicable-migration-required/);
assert.match(platform, /glaze_ui:\n\s+result:\s+applicable-migration-required\n\s+version:\s+1\.3\.0/);
assert.ok(platform.includes('glaze_ui_required: "1.4.1"'));
assert.ok(platform.includes('glaze-ui==1.4.1'));
assert.ok(platform.includes('conformance:\n  status: nonconformant'));
assert.ok(!platform.includes('glaze-ui==1.5.0-dev.1'));
assert.ok(!platform.includes('glaze_ui_required: "1.5.0-dev.1"'));

const upstreamRegistry = JSON.parse(fs.readFileSync(path.join(glazeRoot, 'registry/development/glaze-v1.5.0-dev.1.json'), 'utf8'));
const profiles = JSON.parse(fs.readFileSync(path.join(glazeRoot, 'contracts/v1.5/representative-consumers.dev.json'), 'utf8'));
assert.equal(upstreamRegistry.version, expected.developmentVersion);
assert.equal(upstreamRegistry.lifecycle, 'development');
assert.equal(upstreamRegistry.consumerEligible, false);
assert.equal(upstreamRegistry.stableBaseline, expected.stableVersion);
assert.equal(upstreamRegistry.representativeConsumerAcceptanceEstablished, false);
assert.equal(upstreamRegistry.representativeConsumerIntegrationChangesStableTarget, false);
assert.equal(profiles.version, expected.developmentVersion);
assert.equal(profiles.stableConsumerTarget, expected.stableVersion);
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
  assert.equal(result.version, expected.developmentVersion);
  assert.equal(result.lifecycle, 'development');
  assert.equal(result.stableBaseline, expected.stableVersion);
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

// Scenario 1: canonical Manager profile preserves application refresh authority and policy-owned restricted administration.
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
assert.equal(canonical.authority.automaticNavigationAllowed, false);
assert.equal(JSON.stringify(canonical.diagnostics).includes('manager-policy'), false);
assert.equal(JSON.stringify(canonical.diagnostics).includes('goreecloud-manager-runtime'), false);

// Scenario 2: policy may authorize administration, but Glaze still cannot execute the consequential change or navigate automatically.
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

// Scenario 3: duplicate administrative-authorization ownership fails closed instead of inventing provider precedence.
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

// Scenario 4: application refresh unavailability does not rewrite policy-owned administrative authorization truth.
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

console.log('GoreeCloud Manager / GLAZE UI 1.5.0-dev.1 repository-local Development integration: PASS');
console.log(`Manager exact upstream Glaze revision: ${expected.developmentRevision}`);
console.log('Manager Development scenarios: 4');
console.log(`Manager implemented Glaze source remains: ${expected.implementedVersion}`);
console.log(`Manager required Stable Glaze target remains: ${expected.stableVersion}`);
console.log('Manager V1.5 runtime dependency added: false');
console.log('Manager V1.5 consumer acceptance established: false');
console.log('Manager V1.4.1 migration / Release Candidate / Stable / production acceptance established: false');
